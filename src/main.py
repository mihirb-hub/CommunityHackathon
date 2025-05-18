import streamlit as st
import streamlit_tags as stt
from PIL import Image
import os
import cloudUpload
import time
import io
import json
import gspread
from google.oauth2.service_account import Credentials

# Load initial tags from JSON
try:
    with open("src/tags.json", "r") as f:
        initial_tags = json.load(f)
except FileNotFoundError:
    initial_tags = ["example"]

# Initialize session state
if 'file_uploaded' not in st.session_state:
    st.session_state['file_uploaded'] = False
if 'uploaded_file_data' not in st.session_state:
    st.session_state['uploaded_file_data'] = None
if 'uploaded_file_name' not in st.session_state:
    st.session_state['uploaded_file_name'] = None
if 'uploaded_file_type' not in st.session_state:
    st.session_state['uploaded_file_type'] = None
if 'uploaded_file_size' not in st.session_state:
    st.session_state['uploaded_file_size'] = 0
if 'upload_error' not in st.session_state:
    st.session_state['upload_error'] = None
if 'tags' not in st.session_state:
    st.session_state['tags'] = set(initial_tags)
if 'new_tag' not in st.session_state:
    st.session_state['new_tag'] = ""

# Set page title and header
st.set_page_config(page_title="OMI MetaData Analyzer", layout="centered")
col1c, col2c = st.columns([0.2, 1], vertical_alignment="bottom")
with col1c: 
    st.image("src/imgs/omi_logo.png", width=200)
with col2c:
    st.title(":blue[Okinawa Memories Initiative] Metadata Analyzer", anchor=False)

# Display the initial upload section only if no file is uploaded yet or there's an error
if not st.session_state['file_uploaded'] or st.session_state['upload_error']:
    st.write("""
    This tool allows you to select an image file and have our AI suggest metadata tags.
    """)

    # File uploader widget
    uploaded_file = st.file_uploader(
        "Choose image...",
        type=["jpg", "jpeg", "bmp", "gif"],
        accept_multiple_files=False
        )

    if uploaded_file:
        st.session_state['upload_error'] = None # Reset error state on new upload attempt
        with st.spinner("Processing image...", show_time=True):
            # Simulate a delay for processing
            
            time.sleep(4)

            # --- REPLACE THIS SIMULATION WITH YOUR ACTUAL UPLOAD AND ERROR CHECKING ---
            upload_successful = True  # Replace with your actual upload success check
            upload_error_message = None # Replace with your actual error message if upload fails
             # --- END OF SIMULATION ---

            if upload_successful:
                st.session_state['file_uploaded'] = True
                st.session_state['uploaded_file_data'] = uploaded_file.getvalue()
                st.session_state['uploaded_file_name'] = uploaded_file.name
                st.session_state['uploaded_file_type'] = uploaded_file.type
                st.session_state['uploaded_file_size'] = uploaded_file.size
                st.rerun()
            else:
                st.session_state['upload_error'] = upload_error_message
                st.session_state['file_uploaded'] = False


if st.session_state['file_uploaded']:   
    st.subheader("Uploaded File:", anchor=False)  
    # st.write(f"**File name:** {st.session_state['uploaded_file_name']}")
    # st.write(f"**File type:** {st.session_state['uploaded_file_type']}")
    # st.write(f"**File size:** {st.session_state['uploaded_file_size']} bytes")

    # Display the image
    try:
        image = Image.open(io.BytesIO(st.session_state['uploaded_file_data']))
        st.image(image, caption=f"Uploaded Image: {st.session_state['uploaded_file_name']}", use_container_width=True)
    except Exception as e:
        st.error(f"Error displaying image {st.session_state['uploaded_file_name']}: {e}")
    
    tag_list = list(st.session_state['tags'])

    current_tag_list = stt.st_tags(
        label="## Tags:",
        text='Press enter to add more',
        value=tag_list,
        suggestions=tag_list,
        maxtags = 25,
    )

    col1b, col2b, col3b = st.columns([0.25, 0.15, 0.5], vertical_alignment="center")
    
    with col1b:
        if st.button("Upload Another Image"):
            st.session_state['file_uploaded'] = False
            st.session_state['uploaded_file_data'] = None
            st.session_state['uploaded_file_name'] = None
            st.session_state['uploaded_file_type'] = None
            st.session_state['uploaded_file_size'] = 0
            st.session_state['upload_error'] = None
            st.session_state['tags'] = set(initial_tags)
            # Force a rerun to show the uploader again
            st.rerun()

    with col2b:
        if st.button("Export Tags"):
            # Convert the set of tags to a list
            tags_list = list(current_tag_list)
            # Save the tags to a JSON file
            with open("src/output_tags.json", "w") as f:
                json.dump(tags_list, f)
            with col3b:
                st.success("Tags exported successfully!")

elif st.session_state['upload_error']:
    st.error(f"Error upload failed: {st.session_state['upload_error']}")
    st.info("Please try uploading a valid image file.")
else:
    st.info("Start by uploading an image file using the uploader above.")

st.markdown("---")
st.write("Created with Streamlit.")