import cellpose
import cellpose_omni
from cellpose.models import MODEL_NAMES

for m in ["cyto", "nuclei", "cyto2"]:
    model = cellpose.models.Cellpose(gpu=True, model_type=m)
    if model in ("cyto", "nuclei", "cyto2"):
        size_model_name =  cellpose.models.size_model_path(model)

import urllib.request
import zipfile
import os

url = "https://files.osf.io/v1/resources/xmury/providers/osfstorage/646d978ef4be380b5362bb64/?zip="
filename = "omnipose_models.zip"

try:
    urllib.request.urlretrieve(url, filename)
    print(f"File downloaded successfully to {filename}")
except Exception as e:
    print(f"Error downloading file: {e}")

destination_directory = os.path.expanduser("~/.cellpose/models/")

# Create the destination directory if it doesn't already exist
os.makedirs(destination_directory, exist_ok=True)

try:
    # Open the zip file in read mode ('r')
    with zipfile.ZipFile(filename, 'r') as zip_ref:
        print(f"Extracting all contents of '{filename}' to '{destination_directory}'...")
        # Extract all the contents to the specified directory
        zip_ref.extractall(destination_directory)
except Exception as e:
    print(f"An unexpected error occurred: {e}")