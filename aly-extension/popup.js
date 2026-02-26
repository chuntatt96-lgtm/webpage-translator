let socket;
let recorder;
let audioContext;

document.getElementById("translate").onclick = async () => {

  const selectedLanguage = document.getElementById("language").value;

  socket = new WebSocket("wss://aly-4fof.onrender.com/ws?lang=" + selectedLanguage);

  socket.onopen = () => {
    console.log("WebSocket connected");
    startCapture();
  };

  socket.onmessage = (event) => {
    injectSubtitle(event.data);
  };

  socket.onerror = (e) => {
    console.log("WebSocket error", e);
  };
};

function startCapture() {

  chrome.tabCapture.capture(
    {
      audio: true,
      video: false
    },
    function (stream) {

      // 🔥 FIX: Route audio back to speakers so video is not muted
      audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(audioContext.destination);

      recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

      recorder.ondataavailable = async (event) => {

        if (event.data.size > 0) {
          const arrayBuffer = await event.data.arrayBuffer();

          const base64 = btoa(
            new Uint8Array(arrayBuffer)
              .reduce((data, byte) => data + String.fromCharCode(byte), '')
          );

          if (socket.readyState === WebSocket.OPEN) {
            socket.send(base64);
          }
        }
      };

      recorder.start(2000); // send every 2 seconds
    }
  );
}

function injectSubtitle(text) {

  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {

    chrome.scripting.executeScript({
      target: { tabId: tabs[0].id },
      func: showOverlay,
      args: [text]
    });

  });
}

function showOverlay(text) {

  let div = document.getElementById("aly-subtitles");

  if (!div) {
    div = document.createElement("div");
    div.id = "aly-subtitles";
    div.style.position = "fixed";
    div.style.bottom = "10%";
    div.style.width = "100%";
    div.style.textAlign = "center";
    div.style.color = "white";
    div.style.fontSize = "28px";
    div.style.fontWeight = "bold";
    div.style.textShadow = "2px 2px 6px black";
    div.style.zIndex = "999999";
    document.body.appendChild(div);
  }

  div.innerText = text;
}