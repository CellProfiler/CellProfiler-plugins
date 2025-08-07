import cellpose
from cellpose.models import MODEL_NAMES

for model in MODEL_NAMES:
    for model_index in range(4):
        model_name = cellpose.models.model_path(model, model_index)
    if model in ("cyto", "nuclei", "cyto2"):
        size_model_name =  cellpose.models.size_model_path(model)