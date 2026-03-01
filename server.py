from flask_sock import Sock
from openai import OpenAI
import tempfile
import wave
import struct
import os

sock = Sock()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@sock.route('/ws')
def websocket(ws):

    # Get language from URL
    lang = ws.environ.get("QUERY_STRING", "")
    target_lang = "zh"

    if "lang=" in lang:
        target_lang = lang.split("lang=")[-1]

    print("Target language:", target_lang)

    audio_frames = []

    while True:
        data = ws.receive()
        if data is None:
            break

        audio_frames.append(data)

        # Process every 50 chunks (~few seconds)
        if len(audio_frames) > 50:

            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:

                wf = wave.open(temp_audio.name, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)

                for frame in audio_frames:
                    wf.writeframes(frame)

                wf.close()

                # Transcribe
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=open(temp_audio.name, "rb")
                )

                # Translate
                translation = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Translate to {target_lang}"},
                        {"role": "user", "content": transcript.text}
                    ]
                )

                ws.send(translation.choices[0].message.content)

                audio_frames = []
                os.remove(temp_audio.name)