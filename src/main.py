import streamlit as st
import streamlit_tags as stt
from PIL import Image
import os
import time
import io
# import urllib.parse # No longer needed for keyword extraction URL
import json
# import gspread # Not used directly in main.py based on provided code
# from google.oauth2.service_account import Credentials # Not used directly
import requests

# Configuration for FastAPI backend
FASTAPI_BASE_URL = "http://127.0.0.1:8000"
# UPLOAD_ENDPOINT_URL = f"{FASTAPI_BASE_URL}/uploadfile/" # No longer used for the main analysis flow
# GET_FILE_ENDPOINT_URL_BASE = f"{FASTAPI_BASE_URL}/files/" # Potentially not used if images are displayed from session state
EXTRACT_KEYWORDS_ENDPOINT = f"{FASTAPI_BASE_URL}/extract-keywords/" # Changed: No longer a base, but the direct endpoint

# Load initial tags from JSON
try:
    with open("src/tags.json", "r") as f:
        initial_tags = json.load(f)
except FileNotFoundError:
    initial_tags = ["example"]

# Initialize session state
if 'uploaded_files_info' not in st.session_state:
    st.session_state['uploaded_files_info'] = []

if 'upload_error' not in st.session_state: # Renaming for clarity, or could remove if direct processing has different error states
    st.session_state['analysis_error'] = None

if 'tags' not in st.session_state:
    st.session_state['tags'] = set(initial_tags)

if 'box_number' not in st.session_state:
    st.session_state['box_number'] = 1
if 'folder_number' not in st.session_state:
    st.session_state['folder_number'] = 1

if 'files_analyzed' not in st.session_state:
    st.session_state['files_analyzed'] = False

# Set page title and header
st.set_page_config(page_title="OMI MetaData Analyzer", layout="centered")
col1c, col2c = st.columns([0.2, 1], vertical_alignment="bottom")
with col1c:
    st.image("src/imgs/omi_logo.png", width=200)
with col2c:
    st.title(":blue[Okinawa Memories Initiative] Metadata Analyzer", anchor=False)

# Display the initial upload section only if no file is uploaded yet or there's an error
if not st.session_state['uploaded_files_info'] and not st.session_state.get('analysis_error'): # Adjusted condition
    st.write("""
    This tool allows you to select an image file and have our AI suggest metadata tags.
    Please select a box and folder number to help us organize the image tags.
    """)
    col1d, col2d = st.columns([0.25, 0.25], vertical_alignment="center")
    with col1d:
        boxnumber = st.number_input("Box #", step=1, min_value=1, max_value=25, value=st.session_state['box_number'])
    with col2d:
        foldernumber = st.number_input("Folder #", step=1, min_value=1, max_value=40, value=st.session_state['folder_number'])

    # File uploader widget
    uploaded_file_objects = st.file_uploader( # Renamed for clarity from uploaded_files
        "Choose image(s)...",
        type=["jpg", "jpeg", "bmp", "gif"],
        accept_multiple_files=True
        )

    if st.button("Prepare Images for Analysis"): # Changed button text slightly
        st.session_state['analysis_error'] = None # Reset error state
        st.session_state['uploaded_files_info'] = []  # Clear previous uploads
        st.session_state['files_analyzed'] = False # Reset analysis state
        st.session_state['tags'] = set(initial_tags) # Reset tags

        if uploaded_file_objects:
            for uploaded_file_obj in uploaded_file_objects:
                # Store file info in session state
                file_info = {
                    'key': f"{uploaded_file_obj.name}_{uploaded_file_obj.size}",
                    'name': uploaded_file_obj.name,
                    'type': uploaded_file_obj.type,
                    'size': uploaded_file_obj.size,
                    'data': uploaded_file_obj.getvalue(), # Image data stored here
                    # 'fastapi_filename': None, # No longer needed from a separate upload step
                    # 'upload_status': "pending" # Status can be related to analysis now or removed
                }
                st.session_state['uploaded_files_info'].append(file_info)
            
            # No direct upload to server here anymore, just prepare in session state
            with st.spinner("Preparing images...", show_time=False): # Updated spinner message
                time.sleep(1) # Brief pause to simulate preparation
            st.success(f"{len(st.session_state['uploaded_files_info'])} image(s) ready for analysis.")
            st.rerun() # Rerun to show the gallery and "Analyze Images" button
        else:
            st.warning("Please choose one or more image files.")


elif st.session_state['uploaded_files_info']: # If files are in session state, show gallery and analyze button
    st.subheader("Uploaded Images:", anchor=False)
    num_columns = 3
    for index, file_info in enumerate(st.session_state['uploaded_files_info']):
        if index % num_columns == 0:
            cols = st.columns(num_columns)
        with cols[index % num_columns]:
            try:
                image = Image.open(io.BytesIO(file_info['data']))
                st.image(image, caption=file_info['name'], use_container_width=True)
            except Exception as e:
                st.error(f"Error displaying image {file_info['name']}: {e}")

    if not st.session_state['files_analyzed']: # Show Analyze button only if not yet analyzed
        if st.button("Analyze Images"):
            st.session_state['tags'] = set(initial_tags)  # Reset tags for new analysis
            all_analyses_successful = True

            for file_info in st.session_state['uploaded_files_info']:
                with st.spinner(f"Analyzing {file_info['name']}...", show_time=True):
                    try:
                        # Prepare file for sending: (filename, file_data, content_type)
                        files_payload = {'uploaded_file': (file_info['name'], file_info['data'], file_info['type'])}
                        
                        # Send image data directly to the modified extract-keywords endpoint
                        keyword_response = requests.post(EXTRACT_KEYWORDS_ENDPOINT, files=files_payload, timeout=120)
                        
                        if keyword_response.status_code == 200:
                            keyword_data = keyword_response.json()
                            if keyword_data.get("status") == "success" and keyword_data.get("keywords"):
                                for keyword in keyword_data["keywords"]:
                                    st.session_state['tags'].add(keyword)
                                # Optionally store description if needed:
                                # file_info['description'] = keyword_data.get("description") 
                            elif keyword_data.get("error"):
                                st.error(f"Keyword extraction error for {file_info['name']}: {keyword_data['error']}")
                                all_analyses_successful = False
                        else:
                            st.error(f"Keyword extraction failed for {file_info['name']}: {keyword_response.status_code} - {keyword_response.text}")
                            all_analyses_successful = False
                    except requests.exceptions.RequestException as e:
                        st.error(f"Keyword extraction exception for {file_info['name']}: {e}")
                        all_analyses_successful = False
            
            if all_analyses_successful and st.session_state['uploaded_files_info']:
                 st.session_state['files_analyzed'] = True
            elif not st.session_state['uploaded_files_info']:
                 st.warning("No files were available to analyze.")
            else:
                 st.warning("Some images could not be analyzed. Check errors above.")
            st.rerun()

    if st.session_state['files_analyzed']:
        st.subheader("Generated Tags:", anchor=False)
        tag_list = list(st.session_state['tags'])
        current_tag_list = stt.st_tags(
            label="",
            text='Press enter to add more',
            value=tag_list,
            suggestions=tag_list, # Provide all unique tags as suggestions
            maxtags=25, # Or adjust as needed
        )

        col1b, col2b, col3b = st.columns([0.25, 0.15, 0.5], vertical_alignment="center")

        with col1b:
            if st.button("Process More Images"): # Changed button text
                # Reset relevant session state variables to go back to the uploader
                st.session_state['uploaded_files_info'] = []
                st.session_state['files_analyzed'] = False
                st.session_state['tags'] = set(initial_tags)
                st.session_state['analysis_error'] = None
                # Box and folder numbers could also be reset if desired
                # st.session_state['box_number'] = 1 
                # st.session_state['folder_number'] = 1
                st.rerun()

        with col2b:
            if st.button("Export Tags"):
                tags_to_export = list(current_tag_list) # Use current state of st_tags
                # Save the tags to a JSON file (client-side download might be better for web apps)
                # For now, saving locally as before:
                output_filename = "src/output_tags.json"
                with open(output_filename, "w") as f:
                    json.dump(tags_to_export, f)
                
                # The Google Sheets export is handled by FastAPI.
                # This button could trigger a summary or confirmation.
                with col3b: # Display success message in the third column
                    st.success(f"Tags saved to {output_filename}!")
                    st.info("Image metadata is logged to Google Sheets by the server upon analysis.")
                    
elif st.session_state.get('analysis_error'): # Adjusted to new session state key if changed
    st.error(f"An error occurred: {st.session_state['analysis_error']}")
    st.info("Please try preparing valid image files again.")
else:
    st.info("Start by choosing one or more image files using the uploader above.")

st.markdown("---")
st.write("Created with Streamlit.")