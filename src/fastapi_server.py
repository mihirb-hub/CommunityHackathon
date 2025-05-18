# fastapi_server.py (FastAPI Backend with file serving endpoint - Absolute Path Fix)
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import shutil
import os # os module is crucial for path manipulation
import logging
import mimetypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Define UPLOAD_DIRECTORY using absolute paths ---
# Name of the directory where files will be stored
UPLOAD_DIR_NAME = "uploaded_files_backend"
# Get the absolute path to the directory where this script (fastapi_server.py) is located
# __file__ is a special variable that holds the path to the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Construct the absolute path for the upload directory
UPLOAD_DIRECTORY = os.path.join(SCRIPT_DIR, UPLOAD_DIR_NAME)
# --- End of UPLOAD_DIRECTORY definition ---

# Create the upload directory if it doesn't exist
if not os.path.exists(UPLOAD_DIRECTORY):
    try:
        os.makedirs(UPLOAD_DIRECTORY)
        # Log the absolute path being used
        logger.info(f"Created upload directory at absolute path: {UPLOAD_DIRECTORY}")
    except OSError as e:
        logger.error(f"Could not create upload directory at {UPLOAD_DIRECTORY}: {e}")
else:
    logger.info(f"Upload directory already exists at absolute path: {UPLOAD_DIRECTORY}")


app = FastAPI(
    title="File Upload and Serve API",
    description="A FastAPI backend to receive files from a Streamlit frontend and serve them.",
    version="1.2.0" # Incremented version for this change
)

@app.post("/uploadfile/", tags=["File Operations"])
async def create_upload_file(uploaded_file: UploadFile = File(...)):
    if not uploaded_file:
        logger.warning("Upload attempt with no file.")
        raise HTTPException(status_code=400, detail="No file uploaded. Please select a file.")

    original_filename = uploaded_file.filename or "unnamed_file"
    # Sanitize filename to prevent path traversal issues. os.path.basename is good for this.
    safe_filename = os.path.basename(original_filename)
    
    logger.info(f"Received file: {safe_filename}, Content-Type: {uploaded_file.content_type}, Size: {getattr(uploaded_file, 'size', 'N/A')}")
    # Construct the full absolute path to save the file
    file_location_on_server = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    logger.info(f"Attempting to save file to absolute path: {file_location_on_server}")


    try:
        # Check if UPLOAD_DIRECTORY (now absolute) exists and is writable
        if not os.path.isdir(UPLOAD_DIRECTORY) or not os.access(UPLOAD_DIRECTORY, os.W_OK):
            logger.error(f"Upload directory {UPLOAD_DIRECTORY} is not accessible or writable.")
            raise HTTPException(status_code=500, detail="Server configuration error: Cannot save file.")

        with open(file_location_on_server, "wb+") as file_object:
            shutil.copyfileobj(uploaded_file.file, file_object)
        logger.info(f"File '{safe_filename}' saved successfully to '{file_location_on_server}'")

        response_content = {
            "message": f"File '{safe_filename}' received and saved successfully.",
            "filename_on_server": safe_filename, # This is the name used for retrieval via /files/ endpoint
            "original_filename": original_filename,
            "content_type_at_upload": uploaded_file.content_type,
            # It's generally safer not to expose full server paths in responses unless necessary for a specific reason.
            # "saved_location_on_server": file_location_on_server, 
            "file_size_bytes": getattr(uploaded_file, 'size', None)
        }
        return JSONResponse(status_code=200, content=response_content)
    except HTTPException:
        raise # Re-raise HTTPExceptions directly
    except IOError as e:
        logger.error(f"IOError saving file {safe_filename} to {file_location_on_server}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not save file on server: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing file {safe_filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        try:
            if uploaded_file and hasattr(uploaded_file, 'file') and not uploaded_file.file.closed:
                uploaded_file.file.close()
                logger.debug(f"Closed file stream for {safe_filename}")
        except Exception as e_close:
            logger.error(f"Error closing file stream for {safe_filename}: {e_close}")

@app.get("/files/{filename}", tags=["File Operations"])
async def get_file(filename: str):
    # Sanitize filename from path parameter
    safe_filename = os.path.basename(filename)
    if not safe_filename or safe_filename != filename: # Basic check for path traversal attempts
        logger.warning(f"Attempt to access potentially unsafe filename from URL: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename.")

    # Construct the full absolute path to the requested file
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    logger.info(f"Attempting to serve file from absolute path: {file_path}")

    if not os.path.isfile(file_path): # Check if it's a file and exists
        logger.error(f"File not found at absolute path: {file_path}")
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found.")

    # Guess media type for a better Content-Type header
    media_type, _ = mimetypes.guess_type(file_path)
    if media_type is None:
        media_type = 'application/octet-stream' # Default for unknown binary data

    return FileResponse(path=file_path, media_type=media_type, filename=safe_filename)

@app.get("/", tags=["General"])
async def root():
    return {"message": "FastAPI backend for file upload and serving is running. "
                       "Upload to /uploadfile/, retrieve from /files/{filename}."}
