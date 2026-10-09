from cellcast import models

models_cache = dict()

def init_model(model_name, weights_path, gpu, anisotropy):
    global models_cache

    if model_name == 'stardist2d_fluo':
        cache_key = (model_name, weights_path, gpu)
        model = models_cache.get(cache_key)
        if model is None:
            model = models.StarDist2D.init_fluo(weights_path, gpu)
            models_cache[cache_key] = model
    elif model_name == 'stardist2d_he':
        cache_key = (model_name, weights_path, gpu)
        model = models_cache.get(cache_key)
        if model is None:
            model = models.StarDist2D.init_he(weights_path, gpu)
            models_cache[cache_key] = model
    elif model_name == 'stardist3d_fluo':
        cache_key = (model_name, weights_path, tuple(anisotropy), gpu)
        model = models_cache.get(cache_key)
        if model is None:
            model = models.StarDist3D.init_fluo(weights_path, anisotropy, gpu)
            models_cache[cache_key] = model
    else:
        raise ValueError(f'Unknown model: {model}')
    return model

def predict(data, model_name, weights_path, gpu, prob_threshold=None, nms_threshold=None, anisotropy=None):
    model = init_model(model_name, weights_path, gpu, anisotropy)
    if model_name == 'stardist2d_fluo':
        assert prob_threshold is not None, "Probability threshold not provided"
        assert nms_threshold is not None, "Non-max suprpression threshold not provided"
        labels = model.predict_fluo(data, prob_threshold=prob_threshold, nms_threshold=nms_threshold)
    elif model_name == 'stardist2d_he':
        assert prob_threshold is not None, "Probability threshold not provided"
        assert nms_threshold is not None, "Non-max suprpression threshold not provided"
        labels = model.predict_he(data, prob_threshold=prob_threshold, nms_threshold=nms_threshold)
    elif model_name == 'stardist3d_fluo':
        assert anisotropy is not None, "Anisotropy triple not provided"
        assert prob_threshold is not None, "Probability threshold not provided"
        assert nms_threshold is not None, "Non-max suprpression threshold not provided"
        labels = model.predict_fluo(data, prob_threshold=prob_threshold, nms_threshold=nms_threshold)
    else:
        raise ValueError(f'Unknown model: {model}')
    return labels

if __name__ == "__main__":
    import numpy as np
    data = np.zeros((30,30))
    print(predict(data, 'stardist2d_fluo', None, True, 0.5, 0.3))
