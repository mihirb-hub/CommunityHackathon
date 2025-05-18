# gemini_keyword_extractor.py
import os
from dotenv import load_dotenv
import logging # Make sure logging is imported early if you use logger early

# Configure logging early to see all messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("--- gemini_keyword_extractor.py: Attempting to load .env file ---")
load_dotenv_success = load_dotenv()
logger.info(f"--- gemini_keyword_extractor.py: load_dotenv() executed. Success: {load_dotenv_success} ---")

# Check the critical environment variable
gac_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
gcp_project = os.getenv('GOOGLE_CLOUD_PROJECT_ID')

logger.info(f"--- DEBUG: GOOGLE_APPLICATION_CREDENTIALS after load_dotenv(): {gac_path}")
logger.info(f"--- DEBUG: GOOGLE_CLOUD_PROJECT_ID after load_dotenv(): {gcp_project}")

if gac_path:
    logger.info(f"--- DEBUG: Does the GAC file exist? {os.path.exists(gac_path)}")
else:
    logger.error("--- DEBUG: GOOGLE_APPLICATION_CREDENTIALS is NOT SET in the environment! ---")

# Ensure typing is imported for type hints
from typing import Optional, List, Tuple 

# Google Cloud Vertex AI SDK
import vertexai
from vertexai.generative_models import GenerativeModel, Part, FinishReason
import vertexai.generative_models as generative_models 

# --- Configuration for Vertex AI ---
# Use os.getenv to prefer .env loaded values, with hardcoded as fallback/check
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "omi-photos")
if PROJECT_ID != "omi-photos" and os.getenv("GOOGLE_CLOUD_PROJECT_ID"):
    logger.warning(f"PROJECT_ID used ('{PROJECT_ID}') differs from GOOGLE_CLOUD_PROJECT_ID in .env ('{os.getenv('GOOGLE_CLOUD_PROJECT_ID')}'). Using value from code/default.")
elif not os.getenv("GOOGLE_CLOUD_PROJECT_ID") and PROJECT_ID == "omi-photos":
     logger.info(f"Using hardcoded PROJECT_ID: {PROJECT_ID} as it was not found in .env")


LOCATION = "us-central1"
MODEL_ID = "gemini-2.0-flash-001" 

KEYWORD_GENERATION_PROMPT = "Give 5–25 keywords about this image, each starting with #, and no other information."
SAFETY_SETTINGS = {
    generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

# --- Define _VERTEX_AI_INITIALIZED at the module level BEFORE it's used ---
_VERTEX_AI_INITIALIZED = False # Initialize it here

def _initialize_vertex_ai_client():
    """Initializes the Vertex AI client if not already done."""
    global _VERTEX_AI_INITIALIZED # Declare you intend to modify the global variable
    
    # Now this check is valid because _VERTEX_AI_INITIALIZED has a defined value
    if _VERTEX_AI_INITIALIZED: 
        return True
    
    try:
        if not PROJECT_ID or PROJECT_ID == "YOUR_GOOGLE_CLOUD_PROJECT_ID": # Safeguard
            logger.error("PROJECT_ID is not set correctly in gemini_keyword_extractor.py.")
            return False
            
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        logger.info(f"Vertex AI client initialized successfully for project '{PROJECT_ID}' in '{LOCATION}'.")
        _VERTEX_AI_INITIALIZED = True # Set to True after successful initialization
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI client: {e}", exc_info=True)
        _VERTEX_AI_INITIALIZED = False # Ensure it's False on failure
        return False

def generate_keywords_for_image(
    image_bytes: bytes, 
    mime_type: str, 
    custom_prompt: Optional[str] = None
    ) -> Tuple[Optional[List[str]], Optional[str]]: # Corrected Type Hint
    """
    Generates keywords for an image using the Gemini model.
    Args:
        image_bytes: The raw bytes of the image.
        mime_type: The MIME type of the image (e.g., "image/jpeg", "image/png").
        custom_prompt: An optional custom prompt. If None, uses the default keyword generation prompt.
    Returns:
        A tuple: (list_of_keywords, error_message).
        If successful, list_of_keywords contains strings like "#keyword", and error_message is None.
        If an error occurs, list_of_keywords is None, and error_message contains the error details.
    """
    if not _VERTEX_AI_INITIALIZED: # Check if initialized
        logger.warning("Vertex AI not initialized prior to generate_keywords_for_image call. Attempting to initialize now.")
        if not _initialize_vertex_ai_client(): # Attempt to initialize
            return None, "Error: Vertex AI client could not be initialized. Check server logs."

    prompt_to_use = custom_prompt if custom_prompt is not None else KEYWORD_GENERATION_PROMPT

    try:
        model_instance = GenerativeModel(MODEL_ID, safety_settings=SAFETY_SETTINGS)
        image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
        prompt_part = Part.from_text(prompt_to_use)
        contents_for_sdk = [image_part, prompt_part]

        logger.info(f"Sending request to Gemini model '{MODEL_ID}' for keyword generation. Prompt: '{prompt_to_use[:60]}...'")
        response = model_instance.generate_content(contents_for_sdk)
        
        if not response.candidates:
            logger.warning(f"Gemini response did not contain any candidates. Raw response: {response}")
            error_msg = "Error: No analysis content received from AI or unknown issue (no candidates)."
            if response.prompt_feedback and response.prompt_feedback.block_reason_message:
                error_msg = f"Error: Content blocked by AI. Reason: {response.prompt_feedback.block_reason_message}"
            return None, error_msg

        candidate = response.candidates[0]

        if candidate.finish_reason == FinishReason.SAFETY:
            logger.warning(f"Content blocked by AI due to safety reasons. Finish reason: {candidate.finish_reason.name}")
            block_reason_message = "Content blocked by AI due to safety settings."
            try:
                if response.prompt_feedback and response.prompt_feedback.block_reason_message:
                    block_reason_message = f"Content blocked by AI. Reason: {response.prompt_feedback.block_reason_message}"
                elif candidate.safety_ratings:
                    blocked_categories = [str(sr.category.name) for sr in candidate.safety_ratings if sr.blocked]
                    if blocked_categories:
                         block_reason_message = f"Content blocked due to: {', '.join(blocked_categories)}"
            except Exception as e_safety:
                logger.error(f"Error extracting safety block reason: {e_safety}")
            return None, f"Error: {block_reason_message}"

        if not (candidate.content and candidate.content.parts and candidate.content.parts[0].text):
            logger.warning(f"Gemini response structure not as expected (no text part). Candidate: {candidate}")
            return None, "Error: Received an unexpected response structure from AI (no text part)."
            
        text_response = candidate.content.parts[0].text
        logger.info(f"Successfully received keyword string from Gemini: '{text_response[:100]}...'")
        keywords = [kw.strip() for kw in text_response.split() if kw.startswith('#')]
        
        if not keywords:
            logger.warning(f"No keywords starting with '#' found in Gemini response: '{text_response}'")
            return None, f"No keywords starting with '#' found. Model said: {text_response}"
        return keywords, None
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return None, f"Error: An exception occurred during AI keyword generation: {str(e)}"

# Call initialization when the module is first loaded/imported.
# This ensures that when FastAPI imports this module, an attempt to initialize is made.
_initialize_vertex_ai_client()