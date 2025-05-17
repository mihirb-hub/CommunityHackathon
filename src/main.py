import streamlit as st
from PIL import Image
import os
import cloudUpload

# Set page title and header
st.set_page_config(page_title="Image/Folder Uploader", layout="centered")
st.title("Image or Multi-File Uploader")

st.write("""
This uploader allows you to select one or more image files.
To simulate a 'folder upload', simply select all the desired image files from a folder in the dialog.
""")

# File uploader widget
uploaded_files = st.file_uploader(
    "Choose image(s)...",
    type=["png", "jpg", "jpeg", "bmp", "gif"],
    accept_multiple_files=True
)

if uploaded_files:
    st.subheader("Uploaded File(s):")
    if len(uploaded_files) == 1:
        # Handle single file upload
        uploaded_file = uploaded_files[0]
        
        st.write(f"**File name:** {uploaded_file.name}")
        st.write(f"**File type:** {uploaded_file.type}")
        st.write(f"**File size:** {uploaded_file.size} bytes")

        # Display the image
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption=f"Uploaded Image: {uploaded_file.name}", use_container_width=True)
        except Exception as e:
            st.error(f"Error displaying image {uploaded_file.name}: {e}")

    # else:
    #     # Handle multiple files upload
    #     st.write(f"You have uploaded **{len(uploaded_files)}** files.")
    #     
    #     # Optionally, display all uploaded images (can be slow for many large images)
    #     display_all_images = st.checkbox("Display all uploaded images?", value=True)
    #
    #     for i, uploaded_file in enumerate(uploaded_files):
    #         st.write(f"---")
    #         st.write(f"**File #{i+1}:**")
    #         st.write(f"**Name:** {uploaded_file.name}")
    #         st.write(f"**Type:** {uploaded_file.type}")
    #         st.write(f"**Size:** {uploaded_file.size} bytes")
    #
    #         if display_all_images:
    #             try:
    #                 image = Image.open(uploaded_file)
    #                 # Use columns for a more compact layout if displaying multiple images
    #                 # col1, col2 = st.columns([1, 3])
    #                 # with col1:
    #                 #     st.write(f"Preview of {uploaded_file.name}:")
    #                 # with col2:
    #                 #     st.image(image, width=150) # Display smaller thumbnails
    #                 st.image(image, caption=f"{uploaded_file.name}", width=300)
    #             except Exception as e:
    #                 st.error(f"Error displaying image {uploaded_file.name}: {e}")
else:
    st.info("Upload one or more image files using the uploader above.")

st.markdown("---")
st.write("Created with Streamlit.")