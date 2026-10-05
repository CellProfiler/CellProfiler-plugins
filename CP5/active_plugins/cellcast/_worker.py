"""Pure cellcast segmentation functions, executed only inside the plugin's
Appose-managed subprocess. Never imported by CellProfiler itself."""


def run_stardist2d_fluo(data, weights_path, gpu, prob_threshold, nms_threshold):
    import cellcast.models as models

    model = models.StarDist2D.init_fluo(weights_path, gpu)
    return model.predict_fluo(
        data, prob_threshold=prob_threshold, nms_threshold=nms_threshold
    )


def run_stardist2d_he(data, weights_path, gpu, prob_threshold, nms_threshold):
    import cellcast.models as models

    model = models.StarDist2D.init_he(weights_path, gpu)
    return model.predict_he(
        data, prob_threshold=prob_threshold, nms_threshold=nms_threshold
    )


def run_stardist3d_fluo(
    data, weights_path, anisotropy, gpu, prob_threshold, nms_threshold
):
    import cellcast.models as models

    model = models.StarDist3D.init_fluo(weights_path, anisotropy, gpu)
    return model.predict_fluo(
        data, prob_threshold=prob_threshold, nms_threshold=nms_threshold
    )
