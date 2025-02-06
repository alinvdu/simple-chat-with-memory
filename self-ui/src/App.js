import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import LoginButton from "./components/LoginButton";
import { useAuth } from "./auth/AuthContext";

const api = "https://silver-space-pancake-97w4jq55q9v2xxxg-8000.app.github.dev"

function App() {
  const { token } = useAuth();
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [memories, setMemories] = useState([])

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const mediaSourceRef = useRef(null);
  const readerRef = useRef(null);

  // When the component mounts, fetch a new session ID.
  useEffect(() => {
    const createSession = async () => {
      try {
        const res = await fetch(api + "/new_session", {headers: {
          Authorization: `Bearer ${token}`,
        }});
        const data = await res.json();
        setSessionId(data.session_id);
      } catch (error) {
        console.error("Error creating new session:", error);
      }
    }

    const fetchMemories = async () => {
      try {
        const res = await fetch(api + "/retrieve_memories", {headers: {
          Authorization: `Bearer ${token}`,
        }});
        const data = await res.json();
        setMemories(data.memories)
      } catch (error) {
        console.error("Error creating new session:", error);
      }
    }

    createSession();

    if (token) {
      fetchMemories();
    }
  }, [token]);

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

        // Send the blob to FastAPI server along with session id.
        const formData = new FormData();
        formData.append("file", audioBlob, "recording.mp3");

        // Append session_id as a query parameter
        try {
          const response = await fetch(api + `/process_audio?tts=true&session_id=${sessionId}`, {
            method: "POST",
            body: formData,
            headers: {
              Authorization: `Bearer ${token}`,
            }
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
              if (done) {
                // If we're done reading from the stream, signal end of stream
                if (mediaSourceRef.current.readyState === "open") {
                  try {
                    mediaSourceRef.current.endOfStream();
                  } catch (error) {
                    console.log('error executing end of stream', error);
                  }
                }
                return;
              }
          
              // When this chunk finishes appending, we push the next chunk in updateend
              sourceBuffer.addEventListener('updateend', function onUpdateEnd() {
                sourceBuffer.removeEventListener('updateend', onUpdateEnd);
                pushData();   // call pushData again once the buffer is done updating
              });
          
              try {
                // This puts the buffer into the updating state
                sourceBuffer.appendBuffer(value);
              } catch (err) {
                console.error('Error on buffer append');
                console.error(err);
              }
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
          console.error("Error sending audio:");
          console.error(error)
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
    fetch(api + "/stop_playing", { method: "POST", headers: {
      Authorization: `Bearer ${token}`,
    } }); // Tell backend to stop streaming
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const finalizeSession = async () => {
    const token = await auth.currentUser.getIdToken();
    await fetch(api + `/finalize_conversation?session_id=${sessionId}`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
  };

  const finalizeConversation = async () => {
    if (sessionId && token) {
      try {
        await fetch(api + `/finalize_conversation?session_id=${sessionId}`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (error) {
        console.error("Error finalizing session:", error);
      }
    }
  }

  return (
    <div className="App">
      <LoginButton />
      <h1>Audio Recorder + TTS Response</h1>
      <div style={{ marginBottom: "1rem" }}>
        <button onClick={startRecording} disabled={isRecording || isPlaying || !sessionId}>
          {isRecording ? "Recording..." : "Start Recording"}
        </button>

        <button onClick={() => {
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
      {token ? <button onClick={() => {
        finalizeConversation()
      }}>End Conversation</button> : null}
      {token ? <div>
        <h1>Memories:</h1>
        {memories ? memories.map(memory => <div>{memory}</div>) : null}
      </div> : null}
    </div>
  );
}

export default App;
