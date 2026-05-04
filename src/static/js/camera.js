(function () {
  const overlay = document.getElementById("camera-overlay");
  const video = document.getElementById("camera-feed");
  const canvas = document.getElementById("camera-canvas");
  const controlsLive = document.getElementById("controls-live");
  const controlsPrev = document.getElementById("controls-preview");
  const today = overlay.dataset.today;

  if (!document.getElementById("open-camera")) return;

  let stream = null;
  let facingMode = "environment"; // start on rear camera
  let rotation = 0;

  /**
   * Applies the current rotation to the video element, scaling it up to fill
   * the container without letterboxing when rotated 90/270 degrees.
   */
  function applyVideoRotation() {
    if (rotation % 180 !== 0) {
      const cw = video.parentElement.offsetWidth;
      const ch = video.parentElement.offsetHeight;
      const vw = video.videoWidth || cw;
      const vh = video.videoHeight || ch;
      const scale = Math.max(cw / vh, ch / vw);
      video.style.transform = `rotate(${rotation}deg) scale(${scale})`;
    } else {
      video.style.transform = rotation ? `rotate(${rotation}deg)` : "";
    }
  }

  /**
   * Requests camera access and starts the live video stream.
   * Shows the live controls and hides the preview canvas.
   */
  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode },
        audio: false,
      });
      video.srcObject = stream;
      video.onloadedmetadata = applyVideoRotation;
      video.classList.remove("hidden");
      canvas.classList.add("hidden");
      controlsLive.classList.remove("hidden");
      controlsPrev.classList.add("hidden");
    } catch (err) {
      alert("Could not access camera: " + err.message);
      closeCamera();
    }
  }

  /**
   * Stops all active media tracks and clears the stream reference.
   */
  function stopStream() {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
  }

  /**
   * Stops the stream and hides the camera overlay.
   */
  function closeCamera() {
    stopStream();
    overlay.classList.add("hidden");
  }

  /**
   * Captures the current video frame onto the canvas, applying rotation and
   * scaling down to a max of 1200px on the longest side to limit upload size.
   * Switches the UI from live view to preview mode.
   */
  function capture() {
    const MAX = 1200;
    const vw = video.videoWidth,
      vh = video.videoHeight;
    const scale = Math.min(1, MAX / Math.max(vw, vh));
    const sw = Math.round(vw * scale),
      sh = Math.round(vh * scale);
    const rad = (rotation * Math.PI) / 180;

    canvas.width = rotation % 180 !== 0 ? sh : sw;
    canvas.height = rotation % 180 !== 0 ? sw : sh;

    const ctx = canvas.getContext("2d");
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate(rad);
    ctx.drawImage(video, -sw / 2, -sh / 2, sw, sh);
    canvas.style.transform = "";
    stopStream();
    video.classList.add("hidden");
    canvas.classList.remove("hidden");
    controlsLive.classList.add("hidden");
    controlsPrev.classList.remove("hidden");
  }

  document.getElementById("open-camera").addEventListener("click", () => {
    overlay.classList.remove("hidden");
    startCamera();
  });
  document
    .getElementById("camera-close")
    .addEventListener("click", closeCamera);
  document.getElementById("camera-shutter").addEventListener("click", capture);
  document
    .getElementById("camera-retake")
    .addEventListener("click", startCamera);

  // Switches between rear ("environment") and front ("user") camera
  document.getElementById("camera-flip").addEventListener("click", () => {
    facingMode = facingMode === "environment" ? "user" : "environment";
    stopStream();
    startCamera();
  });

  // Allow pressing Enter in the alt text field to submit
  document.getElementById("camera-alt").addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("camera-use").click();
  });

  /**
   * Encodes the canvas as a JPEG and POSTs it to /submit along with the alt
   * text and today's date. Reloads the page on success to show the gallery.
   */
  document.getElementById("camera-use").addEventListener("click", async () => {
    const imageData = canvas.toDataURL("image/jpeg", 0.82);
    const altText = document.getElementById("camera-alt").value.trim();
    const useBtn = document.getElementById("camera-use");
    useBtn.textContent = "Uploading…";
    useBtn.disabled = true;
    try {
      const res = await fetch("/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: imageData,
          alt_text: altText,
          local_date: today,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Upload failed");
      closeCamera();
      window.location.reload();
    } catch (err) {
      alert("Could not submit: " + err.message);
      useBtn.textContent = "Submit";
      useBtn.disabled = false;
    }
  });
})();
