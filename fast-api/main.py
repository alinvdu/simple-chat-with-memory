from fastapi import FastAPI, File, UploadFile, Query
from fastapi.responses import StreamingResponse, JSONResponse
import os
import uuid
import aiofiles
import tempfile
import asyncio

from openai import OpenAI

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

from fastapi import Query
from datetime import datetime
import uuid

from pinecone import Pinecone

from fastapi import Depends, Header, HTTPException
from typing import Optional

import os
from dotenv import load_dotenv

load_dotenv()

cred = credentials.Certificate("../serviceAccountKey.json")
firebase_admin.initialize_app(cred)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware


origins = [
    "http://localhost:3000",
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

# In-memory conversation history: session_id -> list of messages
conversation_histories = {}

async def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token  # Contains fields like uid, email, etc.
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token invalid or expired")

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index("self")

@app.post("/finalize_conversation")
async def finalize_conversation(
    session_id: str = Query(...),
    user: dict = Depends(verify_token)
):
    # Ensure the session exists.
    if session_id not in conversation_histories:
        return JSONResponse(content={"message": "Session not found."}, status_code=404)
    
    conversation = conversation_histories[session_id]
    # Concatenate conversation messages (system, user, assistant, etc.)
    conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
    
    # Create a prompt for summarization.
    summarization_prompt = (
        "Summarize the following conversation, focusing on key insights and useful context:\n\n" +
        conversation_text
    )
    
    # Use your LLM (e.g., GPT-3.5-turbo) to generate a summary.
    summary_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an expert summarizer."},
            {"role": "user", "content": summarization_prompt}
        ]
    )
    summary_text = summary_response.choices[0].message.content
    print("Summary:", summary_text)
    
    # Check whether the summary is useful to store.
    check_prompt = (
        f"Is the following summary useful enough to store as long term memory? "
        f"Answer with 'yes' or 'no'.\n\n{summary_text}"
    )
    check_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": check_prompt}]
    )
    decision = check_response.choices[0].message.content.strip().lower()
    if "yes" not in decision:
        return JSONResponse(
            content={"message": "Summary deemed not useful for long term memory."}
        )
    
    # Generate a unique record ID.
    record_id = str(uuid.uuid4())
    
    # Create a record dictionary that includes the summary and extra metadata.
    record = {
        "_id": record_id,
        "text": summary_text,   # The summary becomes the text stored.
        "user_id": user["uid"],       # Extra metadata to indicate the owner.
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "category": "conversation_summary"  # You can adjust this as needed.
    }
    
    # Choose a namespace for your user memories (for example, "user-memories").
    namespace = "user-memories"
    
    # Upsert the record into your Pinecone index. With integrated inference,
    # Pinecone will compute the embedding internally using multilingual-e5-large.
    pinecone_index.upsert_records(namespace, [record])
    
    # Optionally, clear the in-memory session history now that it has been finalized.
    del conversation_histories[session_id]
    
    return JSONResponse(content={"message": "Conversation stored in long term memory."})

@app.get("/new_session")
async def new_session():
    """Generate a new session ID and initialize the conversation history."""
    session_id = str(uuid.uuid4())
    # Initialize with a system message
    conversation_histories[session_id] = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    return {"session_id": session_id}

@app.post("/stop_playing")
async def stop_playing():
    """Signal to stop the currently playing TTS stream."""
    stop_event.set()
    return {"message": "Playback stopping..."}

@app.get("/hello")
def say_hello():
    return {"message": "Hello from FastAPI"}

@app.post("/process_audio")
async def process_audio(
    file: UploadFile = File(...),
    tts: bool = False,
    session_id: str = Query(...),
    user: dict = Depends(verify_token)  # verifies Firebase token and provides user info
):
    """
    Receives an audio file, transcribes it, retrieves relevant long-term memories (if any),
    appends them to the conversation history, and generates a response.
    """
    # 1. Save the uploaded file temporarily.
    file_extension = file.filename.split(".")[-1]
    temp_file_name = f"{uuid.uuid4()}.{file_extension}"
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, temp_file_name)

    stop_event.clear()

    async with aiofiles.open(temp_file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    try:
        # 2. Transcribe the audio using Whisper.
        with open(temp_file_path, "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        user_text = transcript_response.text
        print("User said:", user_text)

        # 3. Retrieve or initialize the session conversation history.
        if session_id not in conversation_histories:
            conversation_histories[session_id] = [
                {"role": "system", "content": "You are a helpful assistant."}
            ]
        history = conversation_histories[session_id]

        # 4. If the user is authenticated, retrieve relevant long-term memories.
        #    The search uses Pinecone’s integrated inference.  
        #    We query the "user-memories" namespace for records whose "chunk_text" 
        #    best matches the current user_text.
        if user:
            results = pinecone_index.search_records(
                namespace="user-memories",
                query={
                    "inputs": {"text": user_text},
                    "top_k": 5
                },
                fields=["text"]
            )
            # Extract the summaries (or "chunk_text") from the returned matches.
            # (Assuming that each match returns its fields under a key "fields".)
            memories = []
            result = results['result']
            for match in result.get("hits", []):
                fields = match.get("fields", {})
                if "text" in fields:
                    memories.append(fields["text"])
            # If any memories were found, prepend them to the conversation as context.
            if memories:
                retrieved_memories_text = "Relevant long-term memories:\n" + "\n".join(memories)
                history.append({"role": "system", "content": retrieved_memories_text})

        # 5. Append the new user message to the conversation history.
        history.append({"role": "user", "content": user_text})

        # 6. Generate a response using the full conversation history (with injected memories, if any).
        chat_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=history
        )
        assistant_text = chat_response.choices[0].message.content

        # 7. Append the assistant's response to the conversation history.
        history.append({"role": "assistant", "content": assistant_text})

        # 8. Optionally convert the assistant_text to TTS and stream the audio.
        if tts:
            def audio_stream():
                """Stream the TTS response."""
                with client.audio.speech.with_streaming_response.create(
                    model="tts-1",
                    voice="onyx",
                    input=assistant_text
                ) as response:
                    for chunk in response.iter_bytes():
                        if stop_event.is_set():
                            break
                        yield chunk

            return StreamingResponse(audio_stream(), media_type="audio/mpeg")
        else:
            # Return the plain text response.
            return JSONResponse(
                content={
                    "transcribed_text": user_text,
                    "assistant_text": assistant_text
                }
            )
    except Exception as e:
        print(e)
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        # Clean up the temporary audio file.
        os.remove(temp_file_path)

@app.get("/retrieve_memories")
async def retrieve_memories(user: dict = Depends(verify_token)):
    """
    Retrieve all long-term memories for the current user.
    Uses a dummy vector to retrieve memories based on metadata filtering.
    """
    # Assume the embedding dimension is 1536 (adjust if different)
    dummy_vector = [0.0] * 1024

    # Search Pinecone with metadata filtering
    results = pinecone_index.query(
        vector=dummy_vector,
        top_k=5,
        filter={"user_id": {"$eq": user["uid"]}},
        namespace="user-memories",
        include_metadata=True  # Ensure metadata is returned
    )

    # Extract relevant metadata
    memories = [match["metadata"]["text"] for match in results["matches"]]

    return JSONResponse(content={"memories": memories})

