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

@app.get("/")
def root():
    return {"status": "Aly Live Translator running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    language = websocket.query_params.get("lang", "English")

    while True:
        try:
            data = await websocket.receive_text()

            audio_bytes = base64.b64decode(data)

            with open("temp.webm", "wb") as f:
                f.write(audio_bytes)

            with open("temp.webm", "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=audio_file
                )

            translated = client.responses.create(
                model="gpt-4.1-mini",
                input=f"Translate this to {language}:\n\n{transcription.text}"
            )

            await websocket.send_text(translated.output_text)

        except Exception as e:
            await websocket.send_text("...")