# main.py (Streamlit App)
import streamlit as st
import requests
import urllib.parse
import json
import os # Added os for os.path.splitext

# Configuration for FastAPI backend (remains the same)
FASTAPI_BASE_URL = "http://127.0.0.1:8000"
UPLOAD_ENDPOINT_URL = f"{FASTAPI_BASE_URL}/uploadfile/"
GET_FILE_ENDPOINT_URL_BASE = f"{FASTAPI_BASE_URL}/files/"
EXTRACT_KEYWORDS_ENDPOINT_BASE = f"{FASTAPI_BASE_URL}/extract-keywords/"

st.set_page_config(page_title="OMI Image Keywords", layout="wide")
st.title("Okinawa Memories Initiative (OMI)\nImage Keyword Generator")
st.subheader("Upload an image to get suggested keyword for it.")

# Initialize session state (remains the same)
if 'upload_statuses' not in st.session_state:
    st.session_state.upload_statuses = {}
if 'keyword_results' not in st.session_state:
    st.session_state.keyword_results = {}

uploaded_files = st.file_uploader(
    "Choose image(s)...",
    type=["png", "jpg", "jpeg", "bmp", "gif"],
    accept_multiple_files=True
)

if uploaded_files:
    for uploaded_file_obj in uploaded_files:
        file_key = f"{uploaded_file_obj.name}_{uploaded_file_obj.size}"
        st.markdown(f"---")
        
        col1, col2 = st.columns([1, 2])

        with col1:
            st.write(f"**File:** `{uploaded_file_obj.name}`")
            st.caption(f"({uploaded_file_obj.type}, {uploaded_file_obj.size} bytes)")
            
            if file_key in st.session_state.upload_statuses and \
               st.session_state.upload_statuses[file_key].get('status') == 'success' and \
               st.session_state.upload_statuses[file_key].get('backend_url'):
                st.image(
                    st.session_state.upload_statuses[file_key]['backend_url'], 
                    caption="Uploaded Image", 
                    use_container_width=True
                )
            else:
                st.image(uploaded_file_obj, caption="Image Preview", use_container_width=True)

        with col2:
            # --- UPLOAD LOGIC (remains the same) ---
            if file_key not in st.session_state.upload_statuses or \
               st.session_state.upload_statuses[file_key].get('status') not in ['success', 'pending_upload']:
                
                st.session_state.upload_statuses[file_key] = {'status': 'pending_upload', 'message': 'Preparing to send...'}
                with st.spinner(f"🚀 Uploading {uploaded_file_obj.name} to backend..."):
                    try:
                        file_bytes = uploaded_file_obj.getvalue()
                        files_to_send = {'uploaded_file': (uploaded_file_obj.name, file_bytes, uploaded_file_obj.type)}
                        response = requests.post(UPLOAD_ENDPOINT_URL, files=files_to_send, timeout=60)

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
                    except Exception as e:
                        st.session_state.upload_statuses[file_key] = {'status': 'error', 'message': f"Upload Exception: {str(e)}"}
                st.rerun()

            current_upload_status = st.session_state.upload_statuses.get(file_key)

            if current_upload_status:
                if current_upload_status['status'] == 'success':
                    st.success(current_upload_status['message'])
                    
                    filename_for_keywords = current_upload_status.get('filename_on_server')
                    if filename_for_keywords:
                        st.markdown("---")
                        st.subheader("Keyword Extraction")
                        
                        # --- REMOVED Optional custom prompt text area ---
                        # override_prompt = st.text_area(...) 

                        if st.button(f"Generate Keywords for '{uploaded_file_obj.name}'", key=f"keywords_{file_key}"):
                            st.session_state.keyword_results[file_key] = {'status': 'pending', 'keywords': [], 'error': None}
                            with st.spinner("🤖 Contacting AI for keywords..."):
                                try:
                                    encoded_filename_for_keywords = urllib.parse.quote(filename_for_keywords)
                                    keyword_url = f"{EXTRACT_KEYWORDS_ENDPOINT_BASE}{encoded_filename_for_keywords}"
                                    
                                    # --- MODIFIED: Call POST without a JSON body for the prompt ---
                                    # The FastAPI endpoint will now ignore the body for prompt purposes.
                                    keyword_response = requests.post(keyword_url, timeout=120) 

                                    if keyword_response.status_code == 200:
                                        keyword_data = keyword_response.json()
                                        if keyword_data.get("status") == "success":
                                            st.session_state.keyword_results[file_key] = {
                                                'status': 'success',
                                                'keywords': keyword_data.get("keywords", []),
                                                'error': None,
                                                'prompt_info': f"Prompt used: {keyword_data.get('prompt_text_sent_to_module', 'Default Keyword Prompt')}"
                                            }
                                        else:
                                            st.session_state.keyword_results[file_key] = {
                                                'status': 'error',
                                                'keywords': [],
                                                'error': keyword_data.get("error", "Keyword extraction failed."),
                                                'prompt_info': f"Attempted prompt: {keyword_data.get('prompt_text_sent_to_module', 'Default Keyword Prompt')}"
                                            }
                                    else:
                                        st.session_state.keyword_results[file_key] = {
                                            'status': 'error', 'keywords': [], 'error': f"Keyword Endpoint Error: {keyword_response.status_code} - {keyword_response.text}"
                                        }
                                except Exception as e_keywords:
                                    st.session_state.keyword_results[file_key] = {
                                        'status': 'error', 'keywords': [], 'error': f"Keyword Request Exception: {str(e_keywords)}"
                                    }
                            st.rerun()

                        current_keyword_result = st.session_state.keyword_results.get(file_key)
                        if current_keyword_result:
                            if current_keyword_result['status'] == 'pending':
                                st.info("⏳ Generating keywords...")
                            elif current_keyword_result['status'] == 'success':
                                st.success("Keywords generated successfully!")
                                if current_keyword_result.get('prompt_info'):
                                    st.caption(current_keyword_result['prompt_info'])
                                if current_keyword_result['keywords']:
                                    st.write(current_keyword_result['keywords'])
                                    json_keywords_data = {
                                        "file": filename_for_keywords,
                                        "keywords": current_keyword_result['keywords'],
                                        "prompt_info": current_keyword_result.get('prompt_info')
                                    }
                                    st.download_button(
                                        label="Download Keywords as JSON",
                                        data=json.dumps(json_keywords_data, indent=2),
                                        file_name=f"{os.path.splitext(filename_for_keywords)[0]}_keywords.json",
                                        mime="application/json",
                                        key=f"download_keywords_{file_key}"
                                    )
                                else:
                                    st.write("No keywords were extracted.")
                            elif current_keyword_result['status'] == 'error':
                                st.error(f"Keyword Generation Error: {current_keyword_result['error']}")
                                if current_keyword_result.get('prompt_info'):
                                    st.caption(current_keyword_result['prompt_info'])
                
                elif current_upload_status['status'] == 'error':
                    st.error(current_upload_status['message'])
                elif current_upload_status['status'] == 'pending_upload':
                    st.info(f"⏳ Uploading {uploaded_file_obj.name}...")

    # Cleanup logic (remains the same)
    current_file_keys_in_uploader = {f"{f.name}_{f.size}" for f in uploaded_files}
    for key_to_remove in list(st.session_state.upload_statuses.keys()):
        if key_to_remove not in current_file_keys_in_uploader:
            del st.session_state.upload_statuses[key_to_remove]
            if key_to_remove in st.session_state.keyword_results:
                del st.session_state.keyword_results[key_to_remove]

elif not uploaded_files and (st.session_state.upload_statuses or st.session_state.keyword_results) :
    st.session_state.upload_statuses = {}
    st.session_state.keyword_results = {}
    st.info("Upload one or more image files using the uploader above.")
else:
    st.info("Upload one or more image files using the uploader above.")

st.markdown("---")
# ... (How to Run This Example section remains the same, ensure gemini_keyword_extractor.py is mentioned)
st.markdown(f"""
1.  **Save `gemini_keyword_extractor.py`** (ensure `PROJECT_ID = "omi-photos"` is set).
2.  **Save the FastAPI code above** as `fastapi_server.py` in the same directory.
3.  **Save this Streamlit code** as `main.py` in the same directory.
4.  **Install necessary libraries:**
    ```bash
    pip install streamlit requests fastapi uvicorn python-multipart Pillow google-cloud-aiplatform vertexai
    ```
5.  **Set up Google Cloud Authentication** (as described previously).
6.  **Run the FastAPI backend:**
    ```bash
    uvicorn fastapi_server:app --reload --host 0.0.0.0 --port 8000
    ```
7.  **Run the Streamlit app:**
    ```bash
    streamlit run main.py
    ```
""")