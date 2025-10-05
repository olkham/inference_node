"""
InferNode - Scalable Inference Platform

A distributed inference platform for AI/ML workloads with auto-discovery,
telemetry, and flexible result publishing.
"""

# Import version from canonical location
try:
    from InferenceNode._version import __version__
except ImportError:
    __version__ = "0.1.0"

__author__ = "Oliver Hamilton"
__email__ = "olkhamsoft@gmail.com"
__description__ = "Scalable inference platform with multi-node management and control"

# Public API - only expose what users should import
__all__ = [
    '__version__',
    '__author__',
    '__email__',
    '__description__'
]

# Note: Main components should be imported directly from their modules:
# from InferenceNode.inference_node import InferenceNode
# from InferenceEngine import InferenceEngineFactory
# from ResultPublisher import ResultPublisher, ResultDestination
