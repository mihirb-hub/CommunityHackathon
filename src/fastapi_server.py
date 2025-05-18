# fastapi_server.py
import os
import shutil
import logging
import mimetypes
# from typing import Optional # No longer needed if KeywordRequest is removed

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
# from pydantic import BaseModel # No longer needed if KeywordRequest is removed

# --- Import your new module ---
import gemini_keyword_extractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- UPLOAD_DIRECTORY setup (remains the same) ---
UPLOAD_DIR_NAME = "uploaded_files_backend"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIRECTORY = os.path.join(SCRIPT_DIR, UPLOAD_DIR_NAME)
if not os.path.exists(UPLOAD_DIRECTORY):
    try:
        os.makedirs(UPLOAD_DIRECTORY)
        logger.info(f"Created upload directory at: {UPLOAD_DIRECTORY}")
    except OSError as e:
        logger.error(f"Could not create upload directory at {UPLOAD_DIRECTORY}: {e}")
else:
    logger.info(f"Upload directory already exists at: {UPLOAD_DIRECTORY}")


app = FastAPI(
    title="File Upload, Serve, and AI Keyword Extraction API",
    description="FastAPI backend to receive files, serve them, and extract keywords using a fixed Gemini prompt.",
    version="1.4.1" # Incremented version
)

@app.on_event("startup")
async def startup_event():
    if gemini_keyword_extractor._VERTEX_AI_INITIALIZED:
        logger.info("FastAPI started. Vertex AI initialization in gemini_keyword_extractor was successful.")
    else:
        logger.warning("FastAPI started, but Vertex AI initialization in gemini_keyword_extractor may have failed. Check logs.")

# --- REMOVE Pydantic Model for KeywordRequest ---
# class KeywordRequest(BaseModel):
# custom_prompt_text: Optional[str] = None

# --- Existing Endpoints (/uploadfile/, /files/{filename}) - No changes needed ---
# ... (keep your /uploadfile/ and /files/{filename} endpoints exactly as they are) ...
@app.post("/uploadfile/", tags=["File Operations"])
async def create_upload_file(uploaded_file: UploadFile = File(...)):
    # ... (Keep your existing upload logic from fastapi_server.py)
    if not uploaded_file:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    original_filename = uploaded_file.filename or "unnamed_file"
    safe_filename = os.path.basename(original_filename)
    file_location_on_server = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    try:
        with open(file_location_on_server, "wb+") as file_object:
            shutil.copyfileobj(uploaded_file.file, file_object)
        logger.info(f"File '{safe_filename}' saved to '{file_location_on_server}'")
        return JSONResponse(status_code=200, content={
            "message": "File saved successfully.",
            "filename_on_server": safe_filename,
            "original_filename": original_filename, # Added for consistency with previous version
            "content_type_at_upload": uploaded_file.content_type, # Added
            "file_size_bytes": getattr(uploaded_file, 'size', None) # Added
        })
    except Exception as e:
        logger.error(f"Error saving file {safe_filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        if uploaded_file and hasattr(uploaded_file, 'file') and not uploaded_file.file.closed:
            uploaded_file.file.close()


@app.get("/files/{filename}", tags=["File Operations"])
async def get_file(filename: str):
    # ... (Keep your existing file serving logic from fastapi_server.py)
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    media_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(path=file_path, media_type=media_type or 'application/octet-stream', filename=safe_filename)

# --- MODIFIED Endpoint for Keyword Extraction ---
# Kept as POST for consistency, but doesn't need a request body for the prompt anymore.
@app.post("/extract-keywords/{filename}", tags=["AI Operations"])
async def trigger_keyword_extraction(filename: str): # Removed request_data
    if not gemini_keyword_extractor._VERTEX_AI_INITIALIZED:
        raise HTTPException(status_code=503, detail="AI service (Vertex AI via keyword extractor) is not available.")

    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    if not os.path.isfile(file_path):
        logger.error(f"Image file not found for keyword extraction: {file_path}")
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found for keyword extraction.")

    prompt_source_info = "Module Default (Keywords)"

    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or 'application/octet-stream'

        logger.info(f"Requesting keyword extraction for {safe_filename} using default prompt.")
        
        # Call the function from gemini_keyword_extractor module.
        # Since we don't pass custom_prompt, it will use its internal default.
        keywords_list, error_message = gemini_keyword_extractor.generate_keywords_for_image(
            image_bytes, mime_type # No custom_prompt argument passed
        )
        
        if error_message:
            logger.error(f"Keyword extraction failed for {safe_filename}: {error_message}")
            return JSONResponse(
                status_code=200,
                content={
                    "filename": safe_filename,
                    "keywords": None,
                    "error": error_message,
                    "status": "error",
                    "prompt_used_source": prompt_source_info,
                    "prompt_text_sent_to_module": gemini_keyword_extractor.KEYWORD_GENERATION_PROMPT
                }
            )
        
        logger.info(f"Keyword extraction successful for {safe_filename}: {keywords_list}")
        return JSONResponse(
            status_code=200,
            content={
                "filename": safe_filename,
                "keywords": keywords_list,
                "error": None,
                "status": "success",
                "prompt_used_source": prompt_source_info,
                "prompt_text_sent_to_module": gemini_keyword_extractor.KEYWORD_GENERATION_PROMPT
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error during keyword extraction endpoint for {safe_filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {str(e)}")

@app.get("/", tags=["General"])
async def root():
    return {"message": "FastAPI backend for file upload, serving, and AI keyword extraction is running."}