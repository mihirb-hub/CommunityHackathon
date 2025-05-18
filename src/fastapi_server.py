# fastapi_server.py
import os
import shutil
import logging
import mimetypes

# --- Environment Variable Loading ---
from dotenv import load_dotenv
load_dotenv() 
logger = logging.getLogger(__name__) 
logger.info("FastAPI Server: Attempted to load .env file.")


from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse

import gemini_keyword_extractor # Your updated module

# --- Google Sheets Imports ---
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO) 

# --- Configuration for Google Sheets ---
SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
logger.info(f"FastAPI Server: GOOGLE_APPLICATION_CREDENTIALS read as: {SERVICE_ACCOUNT_FILE}")

SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_ID')
logger.info(f"FastAPI Server: GOOGLE_SHEETS_ID read as: {SPREADSHEET_ID}")


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_NAME_FOR_KEYWORDS = 'Photos' 
# --- MODIFIED HEADERS: Removed "Prompt Used" ---
SHEET_HEADERS = ["Filename", "Keywords", "Description"] 

# --- Initialize Google Sheets Service ---
sheets_service = None
try:
    if not SERVICE_ACCOUNT_FILE:
        logger.error("FastAPI Server: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set OR was not loaded from .env. Google Sheets integration will be disabled.")
    elif not os.path.exists(SERVICE_ACCOUNT_FILE):
        logger.error(f"FastAPI Server: Service account key file NOT FOUND at path specified by GOOGLE_APPLICATION_CREDENTIALS: {SERVICE_ACCOUNT_FILE}. Google Sheets integration will be disabled.")
    elif not SPREADSHEET_ID:
        logger.error("FastAPI Server: GOOGLE_SHEETS_ID environment variable is not set OR was not loaded from .env. Google Sheets integration will be disabled.")
    else:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        sheets_service = build('sheets', 'v4', credentials=creds)
        logger.info(f"FastAPI Server: Google Sheets service initialized successfully for SPREADSHEET_ID: {SPREADSHEET_ID}.")
except Exception as e:
    logger.error(f"FastAPI Server: Failed to initialize Google Sheets service: {e}", exc_info=True)
    sheets_service = None

# --- UPLOAD_DIRECTORY setup ---
UPLOAD_DIR_NAME = "uploaded_files_backend"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIRECTORY = os.path.join(SCRIPT_DIR, UPLOAD_DIR_NAME)
if not os.path.exists(UPLOAD_DIRECTORY):
    try:
        os.makedirs(UPLOAD_DIRECTORY)
        logger.info(f"FastAPI Server: Created upload directory at: {UPLOAD_DIRECTORY}")
    except OSError as e:
        logger.error(f"FastAPI Server: Could not create upload directory at {UPLOAD_DIRECTORY}: {e}")
else:
    logger.info(f"FastAPI Server: Upload directory already exists at: {UPLOAD_DIRECTORY}")

app = FastAPI(
    title="File Upload, Serve, and AI Keyword/Description Extraction API",
    description="FastAPI backend to receive files, serve them, extract keywords and descriptions, and log to a specific Google Sheet (without prompt info).",
    version="1.7.1" # Incremented version
)

def ensure_sheet_with_headers(service, spreadsheet_id, sheet_name, headers):
    if not service:
        logger.error("FastAPI Server (ensure_sheet): Google Sheets service not available.")
        return False
    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', [])
        sheet_exists = False
        
        for sheet_properties in sheets:
            if sheet_properties.get('properties', {}).get('title') == sheet_name:
                sheet_exists = True
                logger.info(f"FastAPI Server (ensure_sheet): Sheet '{sheet_name}' found in SPREADSHEET_ID: {spreadsheet_id}.")
                break

        if not sheet_exists:
            logger.info(f"FastAPI Server (ensure_sheet): Sheet '{sheet_name}' not found in SPREADSHEET_ID: {spreadsheet_id}. Creating it.")
            add_sheet_request = {'addSheet': {'properties': {'title': sheet_name}}}
            body = {'requests': [add_sheet_request]}
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            logger.info(f"FastAPI Server (ensure_sheet): Sheet '{sheet_name}' created.")
            header_body = {'values': [headers]}
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1", 
                valueInputOption='USER_ENTERED',
                body=header_body
            ).execute()
            logger.info(f"FastAPI Server (ensure_sheet): Headers written to new sheet '{sheet_name}'.")
        else:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!1:1" 
            ).execute()
            current_headers = result.get('values', [[]])[0] if result.get('values') else []
            current_headers_str = [str(h).strip() for h in current_headers]
            expected_headers_str = [str(h).strip() for h in headers]

            if current_headers_str != expected_headers_str:
                logger.info(f"FastAPI Server (ensure_sheet): Headers in '{sheet_name}' are missing or incorrect. Current: {current_headers_str}, Expected: {expected_headers_str}. Writing/overwriting headers.")
                header_body = {'values': [headers]}
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption='USER_ENTERED',
                    body=header_body
                ).execute()
                logger.info(f"FastAPI Server (ensure_sheet): Headers updated in sheet '{sheet_name}'.")
            else:
                logger.info(f"FastAPI Server (ensure_sheet): Headers in '{sheet_name}' are correct.")
        return True
    except HttpError as e:
        logger.error(f"FastAPI Server (ensure_sheet): Google API HTTP error for '{sheet_name}': {e.reason}", exc_info=False)
        logger.debug(f"FastAPI Server (ensure_sheet): Full Google API HTTP error details: {e}")
        return False
    except Exception as e:
        logger.error(f"FastAPI Server (ensure_sheet): Unexpected error for '{sheet_name}': {e}", exc_info=True)
        return False

@app.on_event("startup")
async def startup_event():
    if hasattr(gemini_keyword_extractor, '_VERTEX_AI_INITIALIZED') and gemini_keyword_extractor._VERTEX_AI_INITIALIZED:
        logger.info("FastAPI Server: Vertex AI initialization in gemini_keyword_extractor was successful.")
    else:
        logger.warning("FastAPI Server: Vertex AI initialization in gemini_keyword_extractor may have failed or not yet completed. Check gemini_keyword_extractor logs.")

    if sheets_service:
        logger.info("FastAPI Server: Attempting to ensure 'Keywords' sheet exists with headers on startup...")
        if not ensure_sheet_with_headers(sheets_service, SPREADSHEET_ID, SHEET_NAME_FOR_KEYWORDS, SHEET_HEADERS): # Will use new headers
            logger.error(f"FastAPI Server: Failed to ensure '{SHEET_NAME_FOR_KEYWORDS}' sheet is ready on startup. Check permissions and SPREADSHEET_ID.")
    else:
        logger.error("FastAPI Server: Google Sheets service is NOT initialized. Check GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_SHEETS_ID environment variables and .env file loading.")


@app.post("/uploadfile/", tags=["File Operations"])
async def create_upload_file(uploaded_file: UploadFile = File(...)):
    if not uploaded_file:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    original_filename = uploaded_file.filename or "unnamed_file"
    safe_filename = os.path.basename(original_filename).replace("..", "").replace("/", "")
    if not safe_filename: 
        safe_filename = "default_uploaded_file"

    file_location_on_server = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    counter = 0
    base, ext = os.path.splitext(file_location_on_server)
    while os.path.exists(file_location_on_server):
        counter += 1
        file_location_on_server = f"{base}_{counter}{ext}"
        safe_filename = os.path.basename(file_location_on_server)

    try:
        with open(file_location_on_server, "wb+") as file_object:
            shutil.copyfileobj(uploaded_file.file, file_object)
        logger.info(f"FastAPI Server: File '{safe_filename}' saved to '{file_location_on_server}'")
        return JSONResponse(status_code=200, content={
            "message": "File saved successfully.",
            "filename_on_server": safe_filename, 
            "original_filename": original_filename,
            "content_type_at_upload": uploaded_file.content_type,
            "file_size_bytes": getattr(uploaded_file, 'size', None)
        })
    except Exception as e:
        logger.error(f"FastAPI Server: Error saving file {safe_filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        if uploaded_file and hasattr(uploaded_file, 'file') and hasattr(uploaded_file.file, 'closed') and not uploaded_file.file.closed:
            uploaded_file.file.close()


@app.get("/files/{filename}", tags=["File Operations"])
async def get_file(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    media_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(path=file_path, media_type=media_type or 'application/octet-stream', filename=safe_filename)


@app.post("/extract-keywords/{filename}", tags=["AI Operations"])
async def trigger_keyword_extraction(filename: str):
    if not (hasattr(gemini_keyword_extractor, '_VERTEX_AI_INITIALIZED') and gemini_keyword_extractor._VERTEX_AI_INITIALIZED):
        raise HTTPException(status_code=503, detail="AI service (Vertex AI) is not available.")

    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIRECTORY, safe_filename)
    if not os.path.isfile(file_path):
        logger.error(f"FastAPI Server: Image file not found for extraction: {file_path}")
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found for extraction.")

    # prompt_to_display = gemini_keyword_extractor.KEYWORD_DESCRIPTION_PROMPT # No longer needed to send to client

    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or 'application/octet-stream'

        logger.info(f"FastAPI Server: Requesting keywords and description for {safe_filename}.")
        keywords_list, description, error_message = gemini_keyword_extractor.generate_keywords_and_description(
            image_bytes, mime_type
        )

        # --- MODIFIED RESPONSE CONTENT: Removed prompt_used_source and prompt_text_sent_to_module ---
        response_content = {
            "filename": safe_filename,
            "keywords": keywords_list,
            "description": description, 
            "error": error_message,
            "status": "error" if error_message else "success"
            # "prompt_used_source": "Module Default (Keywords & Description)", # REMOVED
            # "prompt_text_sent_to_module": prompt_to_display # REMOVED
        }

        if not error_message and (keywords_list or description): 
            logger.info(f"FastAPI Server: Extraction successful for {safe_filename}. Keywords: {keywords_list}, Desc: {description[:50] if description else 'N/A'}...")
            if sheets_service:
                sheet_ready = ensure_sheet_with_headers(sheets_service, SPREADSHEET_ID, SHEET_NAME_FOR_KEYWORDS, SHEET_HEADERS)
                if sheet_ready:
                    try:
                        keywords_str = ", ".join(keywords_list) if keywords_list else ""
                        # --- MODIFIED ROW TO APPEND: Removed prompt_to_display ---
                        row_to_append = [
                            safe_filename,
                            keywords_str,
                            description if description else ""
                            # prompt_to_display # REMOVED
                        ]
                        value_range_body = {'values': [row_to_append]}
                        
                        sheets_service.spreadsheets().values().append(
                            spreadsheetId=SPREADSHEET_ID,
                            range=f"'{SHEET_NAME_FOR_KEYWORDS}'!A1", 
                            valueInputOption='USER_ENTERED',
                            insertDataOption='INSERT_ROWS', 
                            body=value_range_body
                        ).execute()
                        logger.info(f"FastAPI Server: Successfully appended data for {safe_filename} to Google Sheet '{SHEET_NAME_FOR_KEYWORDS}'.")
                        response_content["sheets_logging_status"] = "success"
                    except HttpError as e_sheet_http:
                        error_details = e_sheet_http.resp.reason if hasattr(e_sheet_http.resp, 'reason') else str(e_sheet_http)
                        if hasattr(e_sheet_http, 'content'):
                             error_details += f" - Details: {e_sheet_http.content.decode() if isinstance(e_sheet_http.content, bytes) else e_sheet_http.content}"
                        logger.error(f"FastAPI Server: Google API HTTP error appending data to Google Sheet for {safe_filename}: {error_details}", exc_info=False)
                        logger.debug(f"FastAPI Server: Full Google API HTTP error details: {e_sheet_http}")
                        response_content["sheets_logging_status"] = "error_api"
                        response_content["sheets_logging_error"] = error_details
                    except Exception as e_sheet:
                        logger.error(f"FastAPI Server: Error appending data to Google Sheet for {safe_filename}: {e_sheet}", exc_info=True)
                        response_content["sheets_logging_status"] = "error"
                        response_content["sheets_logging_error"] = str(e_sheet)
                else:
                    logger.error(f"FastAPI Server: Sheet '{SHEET_NAME_FOR_KEYWORDS}' could not be prepared. Skipping sheet logging for {safe_filename}.")
                    response_content["sheets_logging_status"] = "skipped_sheet_not_ready"
            else:
                logger.warning("FastAPI Server: Google Sheets service not initialized. Skipping sheet logging for {safe_filename}.")
                response_content["sheets_logging_status"] = "skipped_not_initialized"
        elif error_message: 
            logger.error(f"FastAPI Server: Extraction failed for {safe_filename}: {error_message}")
            response_content["status"] = "error"


        return JSONResponse(status_code=200, content=response_content)

    except Exception as e:
        logger.error(f"FastAPI Server: Unexpected error during extraction endpoint for {safe_filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {str(e)}")

@app.get("/", tags=["General"])
async def root():
    return {"message": f"FastAPI backend (v{app.version}) for file upload, serving, AI extraction, and Sheets logging is running."}

