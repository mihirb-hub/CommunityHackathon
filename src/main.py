import streamlit as st
import streamlit_tags as stt
from PIL import Image
import os
import time
import io
import urllib.parse
import json
import gspread
from google.oauth2.service_account import Credentials
import requests

# Configuration for FastAPI backend (remains the same)
FASTAPI_BASE_URL = "http://127.0.0.1:8000"
UPLOAD_ENDPOINT_URL = f"{FASTAPI_BASE_URL}/uploadfile/"
GET_FILE_ENDPOINT_URL_BASE = f"{FASTAPI_BASE_URL}/files/"
EXTRACT_KEYWORDS_ENDPOINT_BASE = f"{FASTAPI_BASE_URL}/extract-keywords/"

# Load initial tags from JSON
try:
    with open("src/tags.json", "r") as f:
        initial_tags = json.load(f)
except FileNotFoundError:
    initial_tags = ["example"]

# Initialize session state
if 'uploaded_files_info' not in st.session_state:
    st.session_state['uploaded_files_info'] = []

if 'upload_error' not in st.session_state:
    st.session_state['upload_error'] = None

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
if not st.session_state['uploaded_files_info'] and not st.session_state['upload_error']:
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
    uploaded_files = st.file_uploader(
        "Choose image(s)...",
        type=["jpg", "jpeg", "bmp", "gif"],
        accept_multiple_files=True
        )

    if st.button("Upload Images"):
        st.session_state['upload_error'] = None # Reset error state on new upload attempt
        st.session_state['uploaded_files_info'] = []  # Clear previous uploads
        for uploaded_file_obj in uploaded_files:
            # file_key helps to identify the file uniquely
            file_info = {
                'key': f"{uploaded_file_obj.name}_{uploaded_file_obj.size}",
                'name': uploaded_file_obj.name,
                'type': uploaded_file_obj.type,
                'size': uploaded_file_obj.size,
                'data': uploaded_file_obj.getvalue(),
                'fastapi_filename': None,
                'upload_status': "pending"
            }
            st.session_state['uploaded_files_info'].append(file_info)
            print(file_info['name'])

        for index, file_info in enumerate(st.session_state['uploaded_files_info']):
            with st.spinner(f"Uploading {file_info['name']}...", show_time=True):
                try:
                    files = {'uploaded_file': (file_info['name'], file_info['data'], file_info['type'])}
                    response = requests.post(UPLOAD_ENDPOINT_URL, files=files, timeout=60)
                    if response.status_code == 200:
                        response_data = response.json()
                        file_info['fastapi_filename'] = response_data.get("filename_on_server")
                        file_info['upload_status'] = "success"
                    else:
                        file_info['upload_status'] = "error"
                        st.error(f"Upload error for {file_info['name']}: {response.status_code} - {response.text}")
                except requests.exceptions.RequestException as e:
                    file_info['upload_status'] = "error"
                    st.error(f"Upload exception for {file_info['name']}: {e}")
        with st.spinner("Waiting...", show_time=True):
            time.sleep(2)
        st.rerun()
# NO LONGER DISPLAYING UPLOAD WIDGET, Display the uploaded images
elif st.session_state['uploaded_files_info']:
    st.subheader("Uploaded Images:", anchor=False)
    num_columns = 3  # You can adjust the number of columns in your gallery
    for index, file_info in enumerate(st.session_state['uploaded_files_info']):
        print(file_info['name'])
        if index % num_columns == 0:
            cols = st.columns(num_columns)
        with cols[index % num_columns]:
            try:
                image = Image.open(io.BytesIO(file_info['data']))
                st.image(image, caption=file_info['name'], use_container_width=True)
            except Exception as e:
                st.error(f"Error displaying image {file_info['name']}: {e}")


    if st.button("Analyze Images"):
        st.session_state['tags'] = set(initial_tags)  # Reset tags for new analysis
        st.session_state['files_analyzed'] = True
        for file_info in st.session_state['uploaded_files_info']:
            if file_info['fastapi_filename']:
                keyword_url = f"{EXTRACT_KEYWORDS_ENDPOINT_BASE}{urllib.parse.quote(file_info['fastapi_filename'])}"
                try:
                    with st.spinner(f"Analyzing {file_info['name']}...", show_time=True):
                        keyword_response = requests.post(keyword_url, timeout=120)
                        if keyword_response.status_code == 200:
                            keyword_data = keyword_response.json()
                            if keyword_data.get("status") == "success" and keyword_data.get("keywords"):
                                for keyword in keyword_data["keywords"]:
                                    st.session_state['tags'].add(keyword)
                            elif keyword_data.get("error"):
                                st.error(f"Keyword extraction error for {file_info['name']}: {keyword_data['error']}")
                        else:
                            st.error(f"Keyword extraction failed for {file_info['name']}: {keyword_response.status_code} - {keyword_response.text}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Keyword extraction exception for {file_info['name']}: {e}")
        st.rerun()
    
    if st.session_state['files_analyzed']:
        st.subheader("Generated Tags:", anchor=False)
        tag_list = list(st.session_state['tags'])
        current_tag_list = stt.st_tags(
            label="",
            text='Press enter to add more',
            value=tag_list,
            suggestions=tag_list,
            maxtags=25,
        )

        col1b, col2b, col3b = st.columns([0.25, 0.15, 0.5], vertical_alignment="center")

        with col1b:
            if st.button("Upload More Images"):
                st.session_state['uploaded_files_info'] = []
                st.session_state['files_analyzed'] = False
                st.session_state['tags'] = set(initial_tags)
                st.rerun()

        with col2b:
            if st.button("Export Tags"):
                tags_to_export = list(current_tag_list)
                # Save the tags to a JSON file
                with open("src/output_tags.json", "w") as f:
                    json.dump(tags_to_export, f)
                # IMPLENT THE FUNCTION TO WRITE TO GOOGLE SHEETS
                with col3b:
                    st.success("Tags exported successfully!")
elif st.session_state['upload_error']:
    st.error(f"Error upload failed: {st.session_state['upload_error']}")
    st.info("Please try uploading valid image files.")
else:
    st.info("Start by uploading one or more image files using the uploader above.")

st.markdown("---")
st.write("Created with Streamlit.")