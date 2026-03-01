from flask_sock import Sock
import threading
import queue

sock = Sock()

# Simple queue system for audio data
audio_queue = queue.Queue()

@sock.route('/ws')
def websocket(ws):

    print("Client connected")

    def receive_audio():
        while True:
            data = ws.receive()
            if data is None:
                break
            audio_queue.put(data)

    def process_audio():
        while True:
            if not audio_queue.empty():
                audio_queue.get()

                # 🔥 Replace this with real translation later
                ws.send("Listening... 🎧")

    t1 = threading.Thread(target=receive_audio)
    t2 = threading.Thread(target=process_audio)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    print("Client disconnected")