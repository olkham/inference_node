import json
from typing import Any, Dict, Optional
from datetime import datetime
try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination

class WebhookDestination(BaseResultDestination):
    """Webhook/HTTP POST result destination"""
    
    def __init__(self):
        super().__init__()
        self.url_template = None  # Store the original URL template with variables
        self.url = None
        self.headers = {}
        self.timeout = 30

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for Webhook destination"""
        base_schema = super().get_config_schema()
        
        webhook_fields = [
            {
                'name': 'url',
                'label': 'Webhook URL',
                'type': 'url',
                'placeholder': 'e.g., http://api.example.com/webhook/{pipeline_id}',
                'description': 'HTTP endpoint URL (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': True
            },
            {
                'name': 'timeout',
                'label': 'Timeout',
                'type': 'number',
                'min': 1,
                'max': 300,
                'placeholder': '30',
                'description': 'Request timeout in seconds',
                'required': False,
                'default': 30,
                'unit': 'seconds'
            },
            {
                'name': 'headers',
                'label': 'Custom Headers',
                'type': 'textarea',
                'placeholder': 'Authorization: Bearer token\nCustom-Header: value',
                'description': 'Optional HTTP headers (one per line, format: Header: Value)',
                'required': False,
                'rows': 3
            }
        ]
        
        # Add webhook-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(webhook_fields)
        return base_schema
    
    def configure(self, url: str, headers: Optional[Dict[str, str]] = None,
                 timeout: int = 30, rate_limit: Optional[float] = None, 
                 max_frames: Optional[int] = None, 
                 include_image_data: bool = False, include_result_image: bool = False) -> None:
        """Configure webhook destination"""
        # Configure common parameters
        self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                            include_image_data=include_image_data, include_result_image=include_result_image)

        # Configure webhook-specific parameters
        self.url_template = url  # Store original template
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout
        self.is_configured = True
        self.logger.info(f"Webhook configured: {url}")
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Publish to webhook URL"""
        try:
            import requests
            
            # Add timestamp
            data["timestamp"] = datetime.utcnow().isoformat()
            
            # Resolve URL with variable substitution
            additional_vars = {}
            if 'pipeline_id' in data:
                additional_vars['pipeline_id'] = data['pipeline_id']
            if 'model_name' in data:
                additional_vars['model_name'] = data['model_name']
            
            resolved_url = self.substitute_variables(self.url_template or '', additional_vars)
            
            response = requests.post(
                resolved_url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                self.logger.debug(f"Published to webhook: {resolved_url}")
                return True
            else:
                # Don't log error here - let base class handle it with failure tracking
                return False
                
        except ImportError:
            # This is a configuration issue, log it once
            self.logger.error("requests package not installed. Install with: pip install requests")
            return False
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False

    def close(self) -> None:
        """Close the webhook connection"""
        self.logger.info(f"Webhook connection closed: {self.url}")