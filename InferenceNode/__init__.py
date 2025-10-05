"""
InferenceNode Package

This package contains the main inference node implementation and supporting components.
"""

from .inference_node import InferenceNode

# Try to import optional components
try:
    from .telemetry import NodeTelemetry
except ImportError:
    NodeTelemetry = None

__version__ = "1.0.0"
__all__ = ["InferenceNode", "NodeTelemetry"]
