document.getElementById("translate").onclick = async () => {
  const text = document.getElementById("text").value;
  const language = document.getElementById("lang").value;

  try {
    const res = await fetch("https://aly-4fof.onrender.com/extension", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language })
    });

    if (!res.ok) {
      throw new Error("Server error: " + res.status);
    }

    const data = await res.json();
    document.getElementById("result").value = data.result || data.error;
  } catch (err) {
    console.error(err);
    document.getElementById("result").value = "Error: " + err.message;
  }
};