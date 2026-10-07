from cellcast import models


def get_model_scaffold(model, weights_path, gpu, prob_threshold=None, nms_threshold=None, anisotropy=None):
    if model == 'stardist2d_fluo':
        assert prob_threshold is not None, "Probability threshold not provided"
        assert nms_threshold is not None, "Non-max suprpression threshold not provided"
        return {
            "cache_key": (model, weights_path, gpu),
            "init": lambda: models.StarDist2D.init_fluo(weights_path, gpu),
            "predict_labels": lambda fluo2d_model, data: fluo2d_model.predict_fluo(data, prob_threshold=prob_threshold, nms_threshold=nms_threshold)
        }
    elif model == 'stardist2d_he':
        assert prob_threshold is not None, "Probability threshold not provided"
        assert nms_threshold is not None, "Non-max suprpression threshold not provided"
        return {
            "cache_key": (model, weights_path, gpu),
            "init": lambda: models.StarDist2D.init_he(weights_path, gpu),
            "predict_labels": lambda he2d_model, data: he2d_model.predict_he(data, prob_threshold=prob_threshold, nms_threshold=nms_threshold)
        }
    elif model == 'stardist3d_fluo':
        assert anisotropy is not None, "Anisotropy triple not provided"
        assert prob_threshold is not None, "Probability threshold not provided"
        assert nms_threshold is not None, "Non-max suprpression threshold not provided"
        return {
            "cache_key": (model, weights_path, tuple(anisotropy), gpu),
            "init": lambda: models.StarDist3D.init_fluo(weights_path, anisotropy, gpu),
            "predict_labels": lambda fluo3d_model, data: fluo3d_model.predict_fluo(data, prob_threshold=prob_threshold, nms_threshold=nms_threshold)
        }
    else:
        raise ValueError(f'Unknown model: {model}')
