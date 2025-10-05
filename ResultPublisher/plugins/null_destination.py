import logging
from typing import Any, Dict, Optional
try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination

class NullDestination(BaseResultDestination):
    """A destination that does nothing (no-op)."""

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for Null destination"""
        # Override to provide only the info field, no common fields
        return {
            'fields': [
                {
                    'name': 'info',
                    'label': 'Information',
                    'type': 'info',
                    'description': 'This destination discards all inference results. No additional configuration is required. This is useful for testing pipelines or viewing live feeds without storing results.',
                    'required': False
                }
            ]
        }

    def configure(self, **kwargs) -> None:
        """Configure null destination (no configuration needed)"""
        self.is_configured = True
        self.logger.info("NullDestination configured (no-op)")

    def _publish(self, data: Dict[str, Any]) -> bool:
        self.logger.debug("NullDestination publish called (no-op)")
        return True

    def close(self) -> None:
        self.logger.info("NullDestination closed (no-op)")