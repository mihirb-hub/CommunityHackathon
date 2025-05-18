# backend/gemini.py

import os
import base64
import requests

from io import BytesIO
from PIL import Image

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse

# ──────────────── 1) Helper to keep Base64 ≤20 KB ────────────────
def make_small_b64(raw: bytes, max_b64_bytes: int = 19_500) -> str:
    """
    Downscale to ≤512×512, then JPEG-compress at Q=90,80…10,
    looping until the Base64 string is ≤ max_b64_bytes.
    """
    img = Image.open(BytesIO(raw))
    img.thumbnail((512, 512))

    last_b64 = ""
    for q in range(90, 9, -10):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=q)
        data = buf.getvalue()
        b64 = base64.b64encode(data).decode("ascii")
        last_b64 = b64
        if len(b64) <= max_b64_bytes:
            return b64

    # fallback if nothing under the cap
    return last_b64

# ──────────────── 2) Config & FastAPI setup ────────────────
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set in environment")

# v1beta2 multimodal endpoint
URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta2/models/gemini-vision-preview:generateMessage"
)

app = FastAPI(title="Image → Hashtags")

@app.get("/", response_class=HTMLResponse)
async def upload_form():
    return """
    <html><body>
      <h1>Upload an Image to Generate Hashtags</h1>
      <form action="/keywords/" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept="image/*" required>
        <button type="submit">Go</button>
      </form>
    </body></html>
    """

# ────────────────── 3) Keyword endpoint ──────────────────
@app.post("/keywords/")
async def keywords(file: UploadFile = File(...)):
    # a) read the image bytes
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload")

    # b) shrink & JPEG-compress until the Base64 ≤20 KB
    img_b64 = make_small_b64(raw, max_b64_bytes=19_500)

    # c) build the payload
    payload = {
        "prompt": {
            "messages": [
                {
                    "author": "user",
                    "content": (
                        "Generate a comma-separated list of 5 to 25 "
                        "concise keywords describing this image."
                    )
                }
            ]
        },
        # <<< must be top-level, not inside "prompt" >>>
        "multimodal": [
            {"image": {"imageBytes": img_b64}}
        ]
    }

    # d) call Gemini
    resp = requests.post(f"{URL}?key={API_KEY}", json=payload)
    if not resp.ok:
        # forward the full error for debugging
        raise HTTPException(resp.status_code, f"{resp.status_code}: {resp.text}")

    body = resp.json()
    # e) parse the returned text
    try:
        text = body["candidates"][0]["content"].strip()
    except Exception:
        raise HTTPException(500, f"Unexpected response format: {body}")

    # f) split, clamp, hashtag-ify
    parts = [p.strip() for p in text.replace("\n", ",").split(",") if p.strip()][:25]
    if len(parts) < 5:
        raise HTTPException(500, f"Too few keywords: {parts}")

    hashtags = " ".join(f"#{w}" for w in parts)
    return {"keywords": hashtags}


# ───────── optional: allow `python gemini.py` ─────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.gemini:app", host="0.0.0.0", port=8000, reload=True)
