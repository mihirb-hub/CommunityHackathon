from streamlit.runtime.uploaded_file_manager import UploadedFile
from typing import List, Dict, Any, Union
import streamlit as st

def prepare_uploaded_files_for_requests(
    uploaded_items: Union[UploadedFile, List[UploadedFile]],
    form_field_name: str
) -> Dict[str, Any]:
    """
    Prepares data from Streamlit UploadedFile objects into the format
    expected by the 'files' parameter of the requests.post() method
    for sending to a web endpoint (like FastAPI).

    Args:
        uploaded_items: A single UploadedFile object or a list of UploadedFile objects
                        obtained from st.file_uploader().
        form_field_name: The string name of the form field that the backend
                         endpoint is expecting the file(s) under (e.g., 'file', 'images').

    Returns:
        A dictionary suitable for the 'files' parameter of requests.post().
        Returns an empty dictionary if no valid items are provided.
    """
    if not form_field_name:
        raise ValueError("form_field_name cannot be empty.")

    # Ensure uploaded_items is treated as a list for consistent processing
    items_list = [uploaded_items] if not isinstance(uploaded_items, list) else uploaded_items

    if not items_list:
        return {} # Return empty dict if no files were uploaded/provided

    # List to hold the file tuples (filename, file_content_bytes, content_type)
    file_tuples = []

    for item in items_list:
        if isinstance(item, UploadedFile):
            try:
                # Get the necessary data from the UploadedFile object
                file_name = item.name
                file_bytes = item.getvalue() # Reads the content as bytes
                content_type = item.type     # Gets the MIME type

                # Append the tuple to the list
                file_tuples.append((file_name, file_bytes, content_type))

            except Exception as e:
                # Handle potential errors reading the file data (less common for UploadedFile)
                print(f"Error processing UploadedFile item: {e}")
                # Decide how to handle this - maybe skip or log

        else:
            # Handle cases where an item in the list is not an UploadedFile
            print(f"Warning: Found non-UploadedFile item in the list: {item}")
            # You might choose to raise an error here depending on strictness

    if not file_tuples:
         # Return empty dict if loop finished but no valid files were added
         return {}

    # The structure for requests 'files' parameter depends on whether
    # the backend expects a single file field or a list of files under the same field name.
    # If the backend expects List[UploadFile] = File(description="Files with same name"):
    # requests format: {'field_name': [(name1, bytes1, type1), (name2, bytes2, type2)]}
    # If the backend expects file1: UploadFile = File(...), file2: UploadFile = File(...):
    # requests format: {'file1': (name1, bytes1, type1), 'file2': (name2, bytes2, type2)}

    # This function prepares for the common List[UploadFile] case, or a single file
    # treated as a list of one.
    # Requests handles a list of tuples for a single field name correctly for List[UploadFile].
    # If you specifically need the {'file1': (...), 'file2': (...)} format, you'd need
    # to change the return structure and perhaps input logic (e.g., take a dict mapping
    # desired backend field names to UploadedFile objects).

    # Return the dictionary formatted for requests' 'files' parameter
    return {form_field_name: file_tuples}

# --- Example Usage within a Streamlit App ---
# (This part is for demonstration within Streamlit)

# import streamlit as st
# import requests # Need requests installed in Streamlit env

# st.title("Streamlit Frontend - Prepare Files for FastAPI")

# FASTAPI_ENDPOINT_URL = "http://localhost:8000/your-fastapi-upload-endpoint/" # <--- REPLACE

# # Use accept_multiple_files=True to get a list
# uploaded_files = st.file_uploader(
#     "Choose image files to prepare",
#     type=["png", "jpg", "jpeg"],
#     accept_multiple_files=True, # Get a list
#     help="Upload one or more images."
# )

# # Assume your FastAPI endpoint expects files under the form field name 'images_to_process'
# backend_field_name = 'images_to_process'


# if st.button("Prepare & Simulate Sending"):
#     if uploaded_files:
#         # Use the function to prepare the data
#         files_payload = prepare_uploaded_files_for_requests(
#             uploaded_files,
#             backend_field_name
#         )

#         st.subheader("Prepared 'files' payload for requests.post():")
#         st.json(files_payload) # Display the structure

#         st.info(f"This payload would be sent to {FASTAPI_ENDPOINT_URL} like this:")
#         st.code(f"""
# import requests
# # ... get uploaded_files and prepare_files_for_requests ...
# files_payload = prepare_uploaded_files_for_requests(uploaded_files, '{backend_field_name}')
#
# try:
#     response = requests.post('{FASTAPI_ENDPOINT_URL}', files=files_payload)
#     # Handle response...
#     st.write("FastAPI Response Status:", response.status_code)
#     st.json(response.json())
# except requests.exceptions.ConnectionError:
#      st.error("Could not connect to FastAPI. Is it running?")
# except Exception as e:
#      st.error(f"Request failed: {{e}}")
# """)

#         # --- To actually send it ---
#         # try:
#         #     st.info(f"Attempting to send to {FASTAPI_ENDPOINT_URL}...")
#         #     response = requests.post(FASTAPI_ENDPOINT_URL, files=files_payload)
#         #     st.subheader("Actual FastAPI Response:")
#         #     st.write("Status Code:", response.status_code)
#         #     st.json(response.json())
#         # except requests.exceptions.ConnectionError:
#         #     st.error(f"Connection Error: Could not connect to FastAPI at {FASTAPI_ENDPOINT_URL}. Make sure it's running.")
#         # except Exception as e:
#         #     st.error(f"An error occurred during the request: {e}")


#     else:
#         st.warning("Please upload files first!")