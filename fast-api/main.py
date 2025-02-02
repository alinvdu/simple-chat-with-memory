from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
import os
import uuid
import aiofiles
import tempfile
import asyncio

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:3000",
    "",
    
    # Add any other origins you need
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stop_event = asyncio.Event()

@app.post("/stop_playing")
async def stop_playing():
    """Signal to stop the currently playing TTS stream."""
    stop_event.set()
    return {"message": "Playback stopping..."}

@app.get("/hello")
def say_hello():
    return {"message": "Hello from FastAPI"}

@app.post("/process_audio")
async def process_audio(file: UploadFile = File(...), tts: bool = False):
    """
    Receives an audio file, transcribes it, generates a response,
    and optionally returns TTS audio.
    """

    # 1. Save the uploaded file to a temp location
    file_extension = file.filename.split(".")[-1]
    temp_file_name = f"{uuid.uuid4()}.{file_extension}"
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, temp_file_name)

    stop_event.clear()

    async with aiofiles.open(temp_file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    try:
        # 2. Transcribe the audio using Whisper
        with open(temp_file_path, "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        user_text = transcript_response.text

        # 3. Generate a response using a Chat or Completion model
        # Example using ChatCompletion (gpt-3.5-turbo)
        chat_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_text}
            ]
        )
        text = chat_response.choices[0].message.content

        # 4. Optionally convert the assistant_text to TTS
        if tts:
            def audio_stream():
                """Generator function to stream TTS response in real-time."""
                with client.audio.speech.with_streaming_response.create(
                    model="tts-1",
                    voice="onyx",
                    input=text
                ) as response:
                    for chunk in response.iter_bytes():
                        if stop_event.is_set():
                            break
                        yield chunk

            return StreamingResponse(audio_stream(), media_type="audio/mpeg")
        else:
            # 5. Return just the text if TTS is not requested
            return JSONResponse(
                content={
                    "transcribed_text": user_text,
                    "assistant_text": text
                }
            )
    except Exception as e:
        print(e)
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        # Clean up temp file(s) if needed
        os.remove(temp_file_path)
