import json
from typing import Any, Dict, Optional
from datetime import datetime
try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination

class ZeroMQDestination(BaseResultDestination):
    """ZeroMQ result destination"""
    
    def __init__(self):
        super().__init__()
        self.socket = None
        self.address_template = None  # Store the original address template with variables
        self.address = None
        self.socket_type = "PUSH"  # Default socket type

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for ZeroMQ destination"""
        base_schema = super().get_config_schema()
        
        zeromq_fields = [
            {
                'name': 'address',
                'label': 'ZeroMQ Address',
                'type': 'text',
                'placeholder': 'e.g., tcp://localhost:5555 or ipc:///tmp/results',
                'description': 'ZeroMQ socket address (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': True
            },
            {
                'name': 'socket_type',
                'label': 'Socket Type',
                'type': 'select',
                'options': [
                    {'value': 'PUSH', 'label': 'PUSH (load balanced)'},
                    {'value': 'PUB', 'label': 'PUB (publish/subscribe)'}
                ],
                'description': 'ZeroMQ socket type for message distribution',
                'required': False,
                'default': 'PUSH'
            }
        ]
        
        # Add ZeroMQ-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(zeromq_fields)
        return base_schema
    
    def configure(self, address: str, socket_type: str = "PUSH", 
                 rate_limit: Optional[float] = None, max_frames: Optional[int] = None,
                 include_image_data: bool = False, include_result_image: bool = False) -> None:
        """Configure ZeroMQ destination"""
        try:
            import zmq
            
            # Configure common parameters
            self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                                include_image_data=include_image_data, include_result_image=include_result_image)
            
            # Configure ZeroMQ-specific parameters
            self.address_template = address  # Store original template
            self.address = address
            self.socket_type = socket_type.upper()
            
            context = zmq.Context()
            
            if self.socket_type == "PUSH":
                self.socket = context.socket(zmq.PUSH)
            elif self.socket_type == "PUB":
                self.socket = context.socket(zmq.PUB)
            else:
                self.logger.error(f"Unsupported ZeroMQ socket type: {self.socket_type}")
                self.is_configured = False
                return
            
            self.socket.connect(address)
            self.is_configured = True
            self.logger.info(f"ZeroMQ configured: {address} ({self.socket_type})")
            
        except ImportError:
            self.logger.error("pyzmq package not installed. Install with: pip install pyzmq")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
        except Exception as e:
            self.logger.error(f"ZeroMQ configuration failed: {str(e)}")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Publish to ZeroMQ socket"""
        try:
            import zmq
            
            # Check if socket is configured and available
            if not self.socket:
                # Don't log error here - let base class handle it with failure tracking
                return False
                
            # Add timestamp
            data["timestamp"] = datetime.utcnow().isoformat()
            
            # Resolve address with variable substitution
            additional_vars = {}
            if 'pipeline_id' in data:
                additional_vars['pipeline_id'] = data['pipeline_id']
            if 'model_name' in data:
                additional_vars['model_name'] = data['model_name']
            
            resolved_address = self.substitute_variables(self.address_template or '', additional_vars)
            
            message = json.dumps(data)
            self.socket.send_string(message)
            
            self.logger.debug(f"Published to ZeroMQ: {resolved_address}")
            return True
            
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False
        
    def close(self) -> None:
        """Close ZeroMQ socket"""
        if self.socket:
            self.socket.close()
            self.logger.info(f"ZeroMQ socket closed: {self.address}")