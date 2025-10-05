from .engines.base_engine import BaseInferenceEngine
from .engines.ultralytics_engine import UltralyticsEngine
from .engines.geti_engine import GetiEngine
from .inference_engine_factory import InferenceEngineFactory

# Import result conversion utilities
from .result_converters import (
    ultralytics_to_geti,
    geti_to_ultralytics,
    # normalize_result_format,
    extract_detections_summary,
    create_rectangle,
    GETI_SDK_AVAILABLE
)
