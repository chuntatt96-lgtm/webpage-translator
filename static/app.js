let socket;
let stream;
let isRunning = false;

document.getElementById("startBtn").addEventListener("click", start);

async function start() {

    if (isRunning) return;
    isRunning = true;

    const language = document.getElementById("language").value;

    socket = new WebSocket(
        (location.protocol === "https:" ? "wss://" : "ws://") +
        location.host +
        "/ws?lang=" + language
    );

    socket.onopen = async () => {

        stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(4096, 1, 1);

        source.connect(processor);
        processor.connect(audioContext.destination);

        processor.onaudioprocess = (event) => {
            const inputData = event.inputBuffer.getChannelData(0);
            socket.send(inputData.buffer);
        };
    };

    socket.onmessage = (event) => {
        document.getElementById("subtitle").innerText = event.data;
    };
}