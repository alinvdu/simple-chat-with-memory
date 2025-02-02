import React, { useState, useRef } from 'react';
import './App.css';

const process_audio_url = ""

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);

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
          const response = await fetch(process_audio_url + "?tts=true", {
            method: "POST",
            body: formData
          });

          if (!response.ok) {
            throw new Error("Server error: " + response.statusText);
          }

          // We expect an mp3 file as the response
          const audioResponseBlob = await response.blob();

          // Create a URL for the received mp3
          const audioUrl = URL.createObjectURL(audioResponseBlob);

          // Play it in the background
          const audio = new Audio(audioUrl);
          setIsPlaying(true);
          audio.play();

          audio.onended = () => {
            // Once playback is done, reset
            setIsPlaying(false);
            setIsRecording(false);
          };

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

          <button onClick={stopRecording} style={{ marginLeft: "1rem" }}>
            Stop Recording
          </button>
      </div>

      {isPlaying && <p>Playing response... Please wait</p>}
      {!isRecording && !isPlaying && <p>Ready to record</p>}
    </div>
  );
}

export default App;
