# Simple Chat With Memory

### Introduction
Simple Chat With Memory is a simple project featuring conversational agent with voice and short + long term memory. It uses openAI API.
- Voice to text: Whisper.
- Text to voice: tts1.
- VectorDB: Pinecone.
- Auth: Firebase.
- UI: React.
- Backend: fast-api.

### Diagram
<img width="1451" alt="Screenshot 2025-02-06 at 23 42 09" src="https://github.com/user-attachments/assets/af56f5a0-c6ec-4ed2-8aa4-d08c8b68b1cb" />

### Running the project
1. Define OPENAI_API_KEY, PINECONE_API_KEY inside /fast-api/.env
2. Define REACT_APP_FIREBASE_API_KEY, REACT_APP_FIREBASE_AUTH_DOMAIN, REACT_APP_FIREBASE_PROJECT_ID, REACT_APP_FIREBASE_STORAGE_BUCKET, REACT_APP_FIREBASE_MESSAGING_SENDER_ID, REACT_APP_FIREBASE_APP_ID inside self-ui/.env
3. cd self-ui -> npm install -> npm start
4. cd fast-api -> pip install -r requirements.txt -> uvicorn main:app --reload
5. Add serviceAccountKey.json into the root from firebase project.

