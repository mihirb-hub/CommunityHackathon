# gemini_keyword_extractor.py
import os
from dotenv import load_dotenv
import logging
import re # Import regular expressions for parsing

# Configure logging early
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("--- gemini_keyword_extractor.py: Attempting to load .env file ---")
load_dotenv_success = load_dotenv()
logger.info(f"--- gemini_keyword_extractor.py: load_dotenv() executed. Success: {load_dotenv_success} ---")

gac_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
gcp_project = os.getenv('GOOGLE_CLOUD_PROJECT_ID')

logger.info(f"--- DEBUG: GOOGLE_APPLICATION_CREDENTIALS after load_dotenv(): {gac_path}")
logger.info(f"--- DEBUG: GOOGLE_CLOUD_PROJECT_ID after load_dotenv(): {gcp_project}")

if gac_path:
    logger.info(f"--- DEBUG: Does the GAC file exist? {os.path.exists(gac_path)}")
else:
    logger.error("--- DEBUG: GOOGLE_APPLICATION_CREDENTIALS is NOT SET in the environment! ---")

from typing import Optional, List, Tuple

import vertexai
from vertexai.generative_models import GenerativeModel, Part, FinishReason
import vertexai.generative_models as generative_models

# --- Configuration for Vertex AI ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "omi-photos")
LOCATION = "us-central1"
MODEL_ID = "gemini-2.0-flash-lite"

# --- NEW PROMPT ---
KEYWORD_DESCRIPTION_PROMPT = (
    "Analyze the image provided.\n"
    "1. Keywords: Generate 5–25 keywords. Each keyword must start with #. Do not include any other text before or after the keywords list." \
        "Ensure that keywords are relevant to important objects or people in the image. Don't create keywords for the sake of propagation." \
        "For context, the keywords are used for archival purposes, so try to use keywords that are relevant to that goal\n." \
    "2. Separator: After the keywords, add a line that says exactly: ---DESCRIPTION---\n"
    "3. Description: Provide a concise 1–3 sentence description of the image.\n"
    "Example Response Structure:\n"
    "#keyword1 #keyword2 #keyword3\n"
    "---DESCRIPTION---\n"
    "This is a short description of the image."
)

SAFETY_SETTINGS = {
    generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

_VERTEX_AI_INITIALIZED = False

def _initialize_vertex_ai_client():
    global _VERTEX_AI_INITIALIZED
    if _VERTEX_AI_INITIALIZED:
        return True
    try:
        if not PROJECT_ID or PROJECT_ID == "YOUR_GOOGLE_CLOUD_PROJECT_ID":
            logger.error("PROJECT_ID is not set correctly in gemini_keyword_extractor.py.")
            return False
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        logger.info(f"Vertex AI client initialized successfully for project '{PROJECT_ID}' in '{LOCATION}'.")
        _VERTEX_AI_INITIALIZED = True
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI client: {e}", exc_info=True)
        _VERTEX_AI_INITIALIZED = False
        return False

def generate_keywords_and_description(
    image_bytes: bytes,
    mime_type: str,
    custom_prompt: Optional[str] = None
) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]: # Keywords, Description, Error
    """
    Generates keywords and a description for an image using the Gemini model.
    Args:
        image_bytes: The raw bytes of the image.
        mime_type: The MIME type of the image (e.g., "image/jpeg", "image/png").
        custom_prompt: An optional custom prompt. If None, uses KEYWORD_DESCRIPTION_PROMPT.
    Returns:
        A tuple: (list_of_keywords, description_text, error_message).
        If successful, list_of_keywords contains strings like "#keyword",
        description_text contains the image description, and error_message is None.
        If an error occurs, list_of_keywords and description_text are None,
        and error_message contains the error details.
    """
    if not _VERTEX_AI_INITIALIZED:
        logger.warning("Vertex AI not initialized. Attempting to initialize now.")
        if not _initialize_vertex_ai_client():
            return None, None, "Error: Vertex AI client could not be initialized."

    prompt_to_use = custom_prompt if custom_prompt is not None else KEYWORD_DESCRIPTION_PROMPT

    try:
        model_instance = GenerativeModel(MODEL_ID, safety_settings=SAFETY_SETTINGS)
        image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
        prompt_part = Part.from_text(prompt_to_use)
        contents_for_sdk = [image_part, prompt_part]

        logger.info(f"Sending request to Gemini model '{MODEL_ID}'. Prompt: '{prompt_to_use[:80]}...'")
        response = model_instance.generate_content(contents_for_sdk)

        if not response.candidates:
            logger.warning(f"Gemini response did not contain any candidates. Raw response: {response}")
            error_msg = "Error: No analysis content received from AI (no candidates)."
            if response.prompt_feedback and response.prompt_feedback.block_reason_message:
                error_msg = f"Error: Content blocked by AI. Reason: {response.prompt_feedback.block_reason_message}"
            return None, None, error_msg

        candidate = response.candidates[0]

        if candidate.finish_reason == FinishReason.SAFETY:
            logger.warning(f"Content blocked by AI due to safety reasons. Finish reason: {candidate.finish_reason.name}")
            block_reason_message = "Content blocked by AI due to safety settings."
            # (Error message extraction logic remains similar)
            return None, None, f"Error: {block_reason_message}"

        if not (candidate.content and candidate.content.parts and candidate.content.parts[0].text):
            logger.warning(f"Gemini response structure not as expected (no text part). Candidate: {candidate}")
            return None, None, "Error: Received an unexpected response structure from AI (no text part)."

        text_response = candidate.content.parts[0].text.strip()
        logger.info(f"Successfully received response from Gemini: '{text_response[:150]}...'")

        # Parse keywords and description
        keywords = []
        description = None
        
        separator = "---DESCRIPTION---"
        if separator in text_response:
            parts = text_response.split(separator, 1)
            keyword_section = parts[0].strip()
            description_section = parts[1].strip() if len(parts) > 1 else ""

            # Extract keywords from the first section
            # Using regex to be more robust with potential leading/trailing text around keywords
            raw_keywords = re.findall(r"#\w+", keyword_section)
            keywords = [kw.strip() for kw in raw_keywords if kw.startswith('#')]
            
            description = description_section
        else:
            # Fallback: try to get keywords if separator is missing, description will be None
            logger.warning(f"Separator '{separator}' not found in response. Attempting to extract only keywords.")
            raw_keywords = re.findall(r"#\w+", text_response)
            keywords = [kw.strip() for kw in raw_keywords if kw.startswith('#')]
            description = "Description not found (separator missing in AI response)."


        if not keywords and not description: # If both are missing, it's likely a parsing or response issue
             logger.warning(f"Could not parse keywords or description from response: '{text_response}'")
             return None, None, f"Could not parse keywords or description. Model said: {text_response}"
        
        if not keywords:
            logger.warning(f"No keywords starting with '#' found in response: '{text_response}'")
            # Decide if this is an error or just a partial success
            # For now, let's return what we have, even if keywords are missing but description is present

        return keywords if keywords else [], description, None # Return empty list if no keywords

    except Exception as e:
        logger.error(f"Error calling Gemini API or parsing response: {e}", exc_info=True)
        return None, None, f"Error: An exception occurred during AI processing: {str(e)}"

_initialize_vertex_ai_client()
