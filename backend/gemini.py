# backend/gemini.py
import os, base64, requests
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

# Note: only ONE "models" in the URL below:
URL = (
  "https://generativelanguage.googleapis.com/"
  "v1beta2/models/gemini-vision-preview:generateMessage"
)

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def form():
    return """
    <html><body>
      <h1>Upload an Image</h1>
      <form action="/keywords/" method="post" enctype="multipart/form-data">
        <input name="file" type="file" accept="image/*" required>
        <button>Go</button>
      </form>
    </body></html>
    """

@app.post("/keywords/")
async def keywords(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")

    img_b64 = base64.b64encode(data).decode("utf-8")
    payload = {
      "prompt": {
        "messages":[
          {"author":"user",
           "content":"Generate a comma-separated list of 5–25 concise keywords describing this image."}
        ],
        "multimodal": [
          {"image": {"imageBytes": img_b64}}
        ]
      }
    }

    resp = requests.post(f"{URL}?key={API_KEY}", json=payload)
    if not resp.ok:
        raise HTTPException(resp.status_code, f"{resp.status_code}: {resp.text}")

    body = resp.json()
    text = body["candidates"][0]["content"]
    tags = [p.strip() for p in text.replace("\n",",").split(",") if p.strip()][:25]
    if len(tags)<5:
        raise HTTPException(500, f"Too few keywords: {tags}")

    return {"keywords": " ".join(f"#{w}" for w in tags)}
