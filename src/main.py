# main.py (Streamlit App)
import streamlit as st
import requests
import urllib.parse
import json
import os # For os.path.splitext

# Configuration for FastAPI backend
FASTAPI_BASE_URL = "http://127.0.0.1:8000" # Ensure this matches your FastAPI host and port
UPLOAD_ENDPOINT_URL = f"{FASTAPI_BASE_URL}/uploadfile/"
GET_FILE_ENDPOINT_URL_BASE = f"{FASTAPI_BASE_URL}/files/"
EXTRACT_KEYWORDS_ENDPOINT_BASE = f"{FASTAPI_BASE_URL}/extract-keywords/" # This endpoint now returns descriptions too

st.set_page_config(page_title="OMI Image Analyzer", layout="wide") # Updated title
st.title("Okinawa Memories Initiative (OMI)\nImage Analyzer") # Updated title
st.subheader("Upload an image to get suggested keywords and a description.") # Updated subheader

# Initialize session state
if 'upload_statuses' not in st.session_state:
    st.session_state.upload_statuses = {}
if 'analysis_results' not in st.session_state: # Renamed from keyword_results for clarity
    st.session_state.analysis_results = {}

uploaded_files = st.file_uploader(
    "Choose image(s)...",
    type=["png", "jpg", "jpeg", "bmp", "gif", "webp"], # Added webp
    accept_multiple_files=True
)

if uploaded_files:
    for uploaded_file_obj in uploaded_files:
        # Use a more robust key that includes original name and size
        file_key = f"{uploaded_file_obj.name}_{uploaded_file_obj.size}"
        st.markdown(f"---")
        
        col1, col2 = st.columns([1, 2]) # Adjust column ratio if needed

        with col1:
            st.write(f"**File:** `{uploaded_file_obj.name}`")
            st.caption(f"({uploaded_file_obj.type}, {uploaded_file_obj.size / 1024:.2f} KB)")
            
            # Display image from backend URL if already uploaded, otherwise show preview
            if file_key in st.session_state.upload_statuses and \
               st.session_state.upload_statuses[file_key].get('status') == 'success' and \
               st.session_state.upload_statuses[file_key].get('backend_url'):
                st.image(
                    st.session_state.upload_statuses[file_key]['backend_url'], 
                    caption="Uploaded Image (from server)", 
                    use_container_width=True
                )
            else:
                st.image(uploaded_file_obj, caption="Image Preview", use_container_width=True)

        with col2:
            # --- UPLOAD LOGIC ---
            if file_key not in st.session_state.upload_statuses or \
               st.session_state.upload_statuses[file_key].get('status') not in ['success', 'pending_upload']:
                
                st.session_state.upload_statuses[file_key] = {'status': 'pending_upload', 'message': 'Preparing to send...'}
                with st.spinner(f"🚀 Uploading {uploaded_file_obj.name} to backend..."):
                    try:
                        file_bytes = uploaded_file_obj.getvalue()
                        files_to_send = {'uploaded_file': (uploaded_file_obj.name, file_bytes, uploaded_file_obj.type)}
                        # Increased timeout for potentially larger files or slower networks
                        response = requests.post(UPLOAD_ENDPOINT_URL, files=files_to_send, timeout=90)

                        if response.status_code == 200:
                            response_data = response.json()
                            filename_on_server = response_data.get("filename_on_server")
                            if filename_on_server:
                                encoded_filename = urllib.parse.quote(filename_on_server)
                                backend_file_url = f"{GET_FILE_ENDPOINT_URL_BASE}{encoded_filename}"
                                st.session_state.upload_statuses[file_key] = {
                                    'status': 'success',
                                    'message': "Image uploaded successfully!",
                                    'data': response_data,
                                    'backend_url': backend_file_url,
                                    'filename_on_server': filename_on_server
                                }
                            else:
                                st.session_state.upload_statuses[file_key] = {'status': 'error', 'message': "Backend did not return a filename."}
                        else:
                            st.session_state.upload_statuses[file_key] = {'status': 'error', 'message': f"Upload Error: {response.status_code} - {response.text}"}
                    except requests.exceptions.RequestException as e_req:
                         st.session_state.upload_statuses[file_key] = {'status': 'error', 'message': f"Upload Network Error: {str(e_req)}"}
                    except Exception as e:
                        st.session_state.upload_statuses[file_key] = {'status': 'error', 'message': f"Upload Exception: {str(e)}"}
                st.rerun() # Rerun to update UI based on new session state

            current_upload_status = st.session_state.upload_statuses.get(file_key)

            if current_upload_status:
                if current_upload_status['status'] == 'success':
                    st.success(current_upload_status['message'])
                    
                    filename_for_analysis = current_upload_status.get('filename_on_server')
                    if filename_for_analysis:
                        st.markdown("---")
                        st.subheader("Image Analysis") # Updated subheader
                        
                        # The custom prompt UI is removed as the backend now uses a fixed, more complex prompt.
                        # If you want to allow custom prompts again, this would need to be re-added
                        # and the FastAPI backend would need to be adjusted to accept it.

                        if st.button(f"Analyze '{uploaded_file_obj.name}'", key=f"analyze_{file_key}"):
                            # Initialize or reset analysis result for this file
                            st.session_state.analysis_results[file_key] = {
                                'status': 'pending', 
                                'keywords': [], 
                                'description': None, # Added description
                                'error': None,
                                'sheets_logging_status': None, # To store sheets logging info
                                'sheets_logging_error': None
                            }
                            with st.spinner("🤖 Contacting AI for analysis (keywords & description)..."):
                                try:
                                    encoded_filename_for_analysis = urllib.parse.quote(filename_for_analysis)
                                    analysis_url = f"{EXTRACT_KEYWORDS_ENDPOINT_BASE}{encoded_filename_for_analysis}"
                                    
                                    # The FastAPI endpoint now uses its internal prompt
                                    analysis_response = requests.post(analysis_url, timeout=180) # Increased timeout

                                    if analysis_response.status_code == 200:
                                        analysis_data = analysis_response.json()
                                        if analysis_data.get("status") == "success":
                                            st.session_state.analysis_results[file_key] = {
                                                'status': 'success',
                                                'keywords': analysis_data.get("keywords", []),
                                                'description': analysis_data.get("description"), # Get description
                                                'error': None,
                                                'prompt_info': f"Prompt used: {analysis_data.get('prompt_text_sent_to_module', 'Default Analysis Prompt')}",
                                                'sheets_logging_status': analysis_data.get('sheets_logging_status'),
                                                'sheets_logging_error': analysis_data.get('sheets_logging_error')
                                            }
                                        else:
                                            st.session_state.analysis_results[file_key] = {
                                                'status': 'error',
                                                'keywords': [],
                                                'description': None,
                                                'error': analysis_data.get("error", "AI analysis failed."),
                                                'prompt_info': f"Attempted prompt: {analysis_data.get('prompt_text_sent_to_module', 'Default Analysis Prompt')}",
                                                'sheets_logging_status': analysis_data.get('sheets_logging_status'),
                                                'sheets_logging_error': analysis_data.get('sheets_logging_error')
                                            }
                                    else:
                                        st.session_state.analysis_results[file_key] = {
                                            'status': 'error', 
                                            'keywords': [], 
                                            'description': None,
                                            'error': f"Analysis Endpoint Error: {analysis_response.status_code} - {analysis_response.text}"
                                        }
                                except requests.exceptions.RequestException as e_analysis_req:
                                    st.session_state.analysis_results[file_key] = {
                                        'status': 'error', 'keywords': [], 'description': None, 'error': f"Analysis Network Error: {str(e_analysis_req)}"
                                    }
                                except Exception as e_analysis:
                                    st.session_state.analysis_results[file_key] = {
                                        'status': 'error', 'keywords': [], 'description': None, 'error': f"Analysis Request Exception: {str(e_analysis)}"
                                    }
                            st.rerun() # Rerun to display results

                        current_analysis_result = st.session_state.analysis_results.get(file_key)
                        if current_analysis_result:
                            if current_analysis_result['status'] == 'pending':
                                st.info("⏳ Generating keywords and description...")
                            elif current_analysis_result['status'] == 'success':
                                st.success("✅ Analysis successful!")
                                if current_analysis_result.get('prompt_info'):
                                    st.caption(current_analysis_result['prompt_info'])
                                
                                # Display Keywords
                                if current_analysis_result['keywords']:
                                    st.markdown("**Keywords:**")
                                    # Display keywords more nicely, perhaps as chips or a formatted string
                                    st.write(", ".join(current_analysis_result['keywords'])) 
                                else:
                                    st.write("No keywords were extracted.")

                                # Display Description
                                if current_analysis_result.get('description'):
                                    st.markdown("**Description:**")
                                    st.write(current_analysis_result['description'])
                                else:
                                    st.write("No description was generated.")

                                # Sheets Logging Status
                                sheets_status = current_analysis_result.get('sheets_logging_status')
                                if sheets_status == 'success':
                                    st.info("📝 Data logged to Google Sheet.")
                                elif sheets_status and sheets_status.startswith('error'):
                                    st.warning(f"⚠️ Error logging to Google Sheet: {current_analysis_result.get('sheets_logging_error', 'Unknown error')}")
                                elif sheets_status == 'skipped_sheet_not_ready':
                                    st.caption("ℹ️ Sheets logging skipped: Sheet not ready on backend.")
                                elif sheets_status == 'skipped_not_initialized':
                                     st.caption("ℹ️ Sheets logging skipped: Service not initialized on backend.")


                                # Download Button
                                if current_analysis_result['keywords'] or current_analysis_result.get('description'):
                                    json_analysis_data = {
                                        "file": filename_for_analysis,
                                        "keywords": current_analysis_result['keywords'],
                                        "description": current_analysis_result.get('description'), # Add description
                                        "prompt_info": current_analysis_result.get('prompt_info'),
                                        "sheets_logging_status": sheets_status,
                                        "sheets_logging_error": current_analysis_result.get('sheets_logging_error')
                                    }
                                    # Generate a more unique filename for download
                                    base_name, _ = os.path.splitext(filename_for_analysis)
                                    st.download_button(
                                        label="Download Analysis as JSON",
                                        data=json.dumps(json_analysis_data, indent=2),
                                        file_name=f"{base_name}_analysis.json",
                                        mime="application/json",
                                        key=f"download_analysis_{file_key}"
                                    )
                            elif current_analysis_result['status'] == 'error':
                                st.error(f"Analysis Error: {current_analysis_result['error']}")
                                if current_analysis_result.get('prompt_info'):
                                    st.caption(current_analysis_result['prompt_info'])
                
                elif current_upload_status['status'] == 'error':
                    st.error(f"Upload Error: {current_upload_status['message']}")
                elif current_upload_status['status'] == 'pending_upload':
                    st.info(f"⏳ Uploading {uploaded_file_obj.name}...")

    # Cleanup logic for files removed from uploader
    current_file_keys_in_uploader = {f"{f.name}_{f.size}" for f in uploaded_files}
    for key_to_remove in list(st.session_state.upload_statuses.keys()): # Iterate over a copy for safe deletion
        if key_to_remove not in current_file_keys_in_uploader:
            del st.session_state.upload_statuses[key_to_remove]
            if key_to_remove in st.session_state.analysis_results: # Use new session state key
                del st.session_state.analysis_results[key_to_remove]

elif not uploaded_files and (st.session_state.upload_statuses or st.session_state.analysis_results) :
    # Clear session state if no files are uploaded but state exists
    st.session_state.upload_statuses = {}
    st.session_state.analysis_results = {} # Use new session state key
    st.info("Upload one or more image files using the uploader above.")
    st.rerun() # Rerun to clear the UI properly
else:
    st.info("Upload one or more image files using the uploader above.")

st.markdown("---")
st.markdown(f"""
### How to Run This Example:
1.  **Save `gemini_keyword_extractor.py`** (the version that generates keywords AND descriptions).
2.  **Save the FastAPI code (`fastapi_server.py`)** that handles keywords, descriptions, and Google Sheets logging.
3.  **Save this Streamlit code** as `main.py` in the same directory.
4.  **Create a `.env` file** in the same directory with:
    ```env
    GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service_account.json"
    GOOGLE_SHEETS_ID="your_spreadsheet_id"
    GOOGLE_CLOUD_PROJECT_ID="omi-photos" 
    ```
    *(Replace with your actual paths and IDs)*
5.  **Install necessary libraries:**
    ```bash
    pip install streamlit requests fastapi uvicorn "python-multipart" Pillow google-cloud-aiplatform vertexai python-dotenv google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
    ```
6.  **Ensure Google Sheets API is enabled** in your Google Cloud Project and your service account has editor access to the target sheet.
7.  **Run the FastAPI backend** (from the directory containing the files):
    ```bash
    uvicorn fastapi_server:app --reload 
    ``` 
    *(Ensure it's running on `http://127.0.0.1:8000` or update `FASTAPI_BASE_URL`)*
8.  **Run the Streamlit app** (from the same directory):
    ```bash
    streamlit run main.py
    ```
""")
