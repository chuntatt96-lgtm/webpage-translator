import os
import base64
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    while True:
        data = await websocket.receive_text()
        audio_bytes = base64.b64decode(data)

        with open("temp.webm", "wb") as f:
            f.write(audio_bytes)

        with open("temp.webm", "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file
            )

        translation = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Translate this to Japanese:\n\n{transcription.text}"
        )

        await websocket.send_text(translation.output_text)