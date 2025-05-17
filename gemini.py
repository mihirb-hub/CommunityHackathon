import os
from fastapi import FastAPI, File, UploadFile, HTTPException
import generativeai as genai
from fastapi.responses import HTMLResponse


# ------------------------------------------------------------------
# 1) Configure Gemini client
# ------------------------------------------------------------------
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=api_key)

# Replace this with the actual multimodal Gemini model name you have access to
MODEL = "models/gemini-vision-preview"

# ------------------------------------------------------------------
# 2) Create your FastAPI app
# ------------------------------------------------------------------
app = FastAPI(title="Image→Keywords with Gemini")
@app.get("/", response_class=HTMLResponse)
async def upload_form():
    return """
    <html>
      <head>
        <title>Image → Keywords</title>
      </head>
      <body>
        <h1>Upload an Image</h1>
        <form action="/keywords/" enctype="multipart/form-data" method="post">
          <input name="file" type="file" accept="image/*" required>
          <button type="submit">Get Hashtags</button>
        </form>
      </body>
    </html>
    """

@app.post("/keywords/")
async def extract_keywords(file: UploadFile = File(...)):
    """
    Accepts an image upload and returns 5–25 descriptive keywords.
    """
    # 2a) read the uploaded image into bytes
    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(400, "Empty file")

    # 2b) call the Gemini multimodal chat endpoint
    try:
        response = genai.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "author": "user",
                    "content": "Generate a comma-separated list of 5 to 25 concise keywords that describe the content of the image."
                }
            ],
            multimodal=[{"image": {"image_bytes": img_bytes}}]
        )
    except Exception as e:
        raise HTTPException(500, f"Gemini API error: {e}")

    # 2c) parse out the comma-separated keywords
    text = response.choices[0].message.content
    # split on commas & newlines, strip whitespace, discard empties
    keywords = [
        kw.strip() 
        for part in text.replace("\n", ",").split(",") 
        for kw in [part] 
        if kw.strip()
    ]
    # clamp to 5–25
    keywords = keywords[:25]
    if len(keywords) < 5:
        raise HTTPException(500, f"Gemini returned too few keywords: {keywords}")

    # prefix each with “#” and join with spaces
    formatted = " ".join(f"#{kw}" for kw in keywords)

    return {"keywords": formatted}


# ------------------------------------------------------------------
# 3) Run with: uvicorn `main`:app --reload
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
