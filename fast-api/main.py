from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
import os
import uuid
import aiofiles
import tempfile

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
            # Create a temporary file to store the generated speech
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name

            # Generate speech from text using OpenAI TTS API
            response = client.audio.speech.create(
                model="tts-1",
                voice="onyx",
                input=text
            )

            # Save the speech to the temporary file
            response.stream_to_file(temp_path)

            # Return the generated MP3 file to the client
            return FileResponse(
                path=temp_path,
                media_type="audio/mpeg",
                filename="output.mp3"
            )
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
