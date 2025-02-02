import React, { useState, useRef } from 'react';
import './App.css';

const api = ""

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const mediaSourceRef = useRef(null);
  const readerRef = useRef(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mediaRecorder = new MediaRecorder(stream);

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }

        // Create a blob from the recorded audio
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/mp3" });
        audioChunksRef.current = [];

        // Send the blob to FastAPI server
        const formData = new FormData();
        formData.append("file", audioBlob, "recording.mp3");

        try {
          const response = await fetch(api + "/process_audio?tts=true", {
            method: "POST",
            body: formData
          });
          if (!response.ok) {
            throw new Error("Server error: " + response.statusText);
          }
  
          // 🎯 Use MediaSource API to stream and play the response
          mediaSourceRef.current = new MediaSource();
          const audioElement = new Audio();
          audioElement.src = URL.createObjectURL(mediaSourceRef.current);
          document.body.appendChild(audioElement); // Ensure it's in the DOM
  
          setIsPlaying(true);
          audioElement.play();

          mediaSourceRef.current.addEventListener("sourceopen", async () => {
            const sourceBuffer = mediaSourceRef.current.addSourceBuffer("audio/mpeg");
            const reader = response.body.getReader();
            readerRef.current = reader;
  
            async function pushData() {
              const { done, value } = await reader.read();
              if (done && mediaSourceRef.current.readyState === "open") {
                try {
                  mediaSourceRef.current.endOfStream();
                } catch (error) {
                  console.log('error executing end of stream', error)
                }
                return;
              }
              try {
                sourceBuffer.appendBuffer(value);
              } catch (err) {
                console.log('Error on buffer', err)
              }
              pushData();
            }
  
            pushData();
  
            // Reset UI when playback ends
            audioElement.onended = () => {
              setIsPlaying(false);
              setIsRecording(false);
            };
          });

          window.currentAudio = audioElement;

        } catch (error) {
          console.error("Error sending audio:", error);
          setIsRecording(false);
          setIsPlaying(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);

    } catch (error) {
      console.error("Error accessing microphone:", error);
    }
  };

  const stopPlaying = () => {
    if (window.currentAudio) {
        if (readerRef.current) {
          console.log('stop reader')
          readerRef.current.cancel();
        }

        window.currentAudio.pause();
        window.currentAudio.currentTime = 0;
        window.currentAudio.src = "";
    }

    setIsPlaying(false);
    fetch(api + "/stop_playing", { method: "POST" }); // Tell backend to stop streaming
}

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  return (
    <div className="App">
      <h1>Audio Recorder + TTS Response</h1>
      <div style={{ marginBottom: "1rem" }}>
        <button onClick={startRecording} disabled={isRecording || isPlaying}>
          {isRecording ? "Recording..." : "Start Recording"}
        </button>

          <button onClick={() => {
            console.log('playing is', isPlaying)
            if (isPlaying) {
              stopPlaying();
            } else {
              stopRecording();
            }
          }} style={{ marginLeft: "1rem" }}>
           {isPlaying ? "Stop Playing" : "Stop Recording"}
          </button>
      </div>

      {isPlaying && <p>Playing response... Please wait</p>}
      {!isRecording && !isPlaying && <p>Ready to record</p>}
    </div>
  );
}

export default App;
