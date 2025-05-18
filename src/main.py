# streamlit_app.py (Adapted from user's main.py with backend retrieval and URL encoding)
import streamlit as st
# from PIL import Image # Not strictly needed if only displaying from URL
import requests
import io
import urllib.parse # Added for URL encoding

# Configuration for FastAPI backend
FASTAPI_BASE_URL = "http://127.0.0.1:8000"  # Base URL of your FastAPI server
UPLOAD_ENDPOINT_URL = f"{FASTAPI_BASE_URL}/uploadfile/"
GET_FILE_ENDPOINT_URL_BASE = f"{FASTAPI_BASE_URL}/files/" # Base for constructing file URLs, ends with a slash

st.set_page_config(page_title="OMI Metadata Generator", layout="centered")
st.title("🖼️ Image Uploader (Streamlit to FastAPI)")
st.subheader("Upload, Store via FastAPI, and Retrieve for Display")

st.write("""
Select one or more image files. Each file will be:
1. Sent to a FastAPI backend.
2. Saved by the backend.
3. Retrieved from the backend and displayed below.
""")

# Initialize session state for tracking upload statuses
if 'upload_statuses' not in st.session_state:
    st.session_state.upload_statuses = {} # Stores: {file_key: {'status': '...', 'message': '...', 'data': {...}, 'backend_url': '...'}}

# File uploader widget
uploaded_files = st.file_uploader(
    "Choose image(s)... (sent automatically)",
    type=["png", "jpg", "jpeg", "bmp", "gif"],
    accept_multiple_files=True
)

if uploaded_files:
    st.subheader(f"Processing {len(uploaded_files)} Uploaded File(s):")

    for uploaded_file_obj in uploaded_files:
        file_key = f"{uploaded_file_obj.name}_{uploaded_file_obj.size}"

        st.markdown(f"---")
        st.write(f"**File:** `{uploaded_file_obj.name}` ({uploaded_file_obj.type}, {uploaded_file_obj.size} bytes)")

        if file_key not in st.session_state.upload_statuses or \
           st.session_state.upload_statuses[file_key].get('status') not in ['success', 'pending_upload']:

            st.session_state.upload_statuses[file_key] = {'status': 'pending_upload', 'message': 'Preparing to send...'}
            with st.spinner(f"🚀 Sending {uploaded_file_obj.name} to FastAPI backend..."):
                try:
                    file_bytes = uploaded_file_obj.getvalue()
                    files_to_send = {'uploaded_file': (uploaded_file_obj.name, file_bytes, uploaded_file_obj.type)}

                    response = requests.post(UPLOAD_ENDPOINT_URL, files=files_to_send, timeout=60)

                    if response.status_code == 200:
                        response_data = response.json()
                        filename_on_server = response_data.get("filename_on_server")
                        if filename_on_server:
                            # URL-encode the filename part to handle special characters safely in URL path
                            encoded_filename = urllib.parse.quote(filename_on_server)
                            backend_file_url = f"{GET_FILE_ENDPOINT_URL_BASE}{encoded_filename}"
                            
                            st.session_state.upload_statuses[file_key] = {
                                'status': 'success',
                                'message': f"✅ Successfully sent and stored by FastAPI!",
                                'data': response_data,
                                'backend_url': backend_file_url  # Store the correctly formed URL
                            }
                        else:
                             st.session_state.upload_statuses[file_key] = {
                                'status': 'error',
                                'message': f"❌ FastAPI did not return a filename_on_server.",
                                'data': response_data
                            }
                    else:
                        st.session_state.upload_statuses[file_key] = {
                            'status': 'error',
                            'message': f"❌ Error sending: {response.status_code} - {response.text}"
                        }
                except requests.exceptions.ConnectionError:
                    st.session_state.upload_statuses[file_key] = {
                        'status': 'error',
                        'message': f"❌ Connection Error: Could not connect to FastAPI at `{FASTAPI_BASE_URL}`."
                    }
                except Exception as e:
                    st.session_state.upload_statuses[file_key] = {
                        'status': 'error',
                        'message': f"❌ An unexpected error occurred during upload: {str(e)}"
                    }
        
        current_status_info = st.session_state.upload_statuses.get(file_key)
        if current_status_info:
            if current_status_info['status'] == 'success':
                st.success(current_status_info['message'])
                backend_url = current_status_info.get('backend_url')
                if backend_url:
                    # This is the primary way to display the image from the backend.
                    # If this shows a link, it means Streamlit cannot load the image from this URL.
                    st.image(backend_url, caption=f"Served from FastAPI: {uploaded_file_obj.name}", use_container_width=True)
                    # For debugging, you can uncomment the next line to see the exact URL being used.
                    st.caption(f"Image URL: {backend_url}") 
                if current_status_info.get('data'):
                    with st.expander("See backend response details"):
                        st.json(current_status_info['data'])
            elif current_status_info['status'] == 'error':
                st.error(current_status_info['message'])
            elif current_status_info['status'] == 'pending_upload':
                st.info(f"⏳ {uploaded_file_obj.name} is queued for upload or being processed...")
    
    current_file_keys = {f"{f.name}_{f.size}" for f in uploaded_files}
    for key_to_check in list(st.session_state.upload_statuses.keys()):
        if key_to_check not in current_file_keys:
            del st.session_state.upload_statuses[key_to_check]

elif not uploaded_files and st.session_state.upload_statuses:
    st.session_state.upload_statuses = {}
    st.info("Upload one or more image files using the uploader above.")
else:
    st.info("Upload one or more image files using the uploader above.")

st.markdown("---")
st.markdown("### How to Run This Example:")
st.markdown(f"""
1.  **Save the FastAPI code** (next code block) as `fastapi_server.py`.
2.  **Install necessary libraries:**
    ```bash
    pip install fastapi uvicorn python-multipart Pillow requests streamlit
    ```
3.  **Run the FastAPI backend (from the directory where `fastapi_server.py` is saved):**
    ```bash
    uvicorn fastapi_server:app --reload
    ```
    (This will typically start the server at `{FASTAPI_BASE_URL}`)
4.  **Save this Streamlit code** as `streamlit_app.py`.
5.  **Run the Streamlit app (from the directory where `streamlit_app.py` is saved):**
    ```bash
    streamlit run streamlit_app.py
    ```
6.  Open your browser and navigate to the Streamlit app's URL (usually `http://localhost:8501`).
7.  Upload one or more image files.
""")
