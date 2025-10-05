import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime
try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination


class MQTTDestination(BaseResultDestination):
    """MQTT result destination"""
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.server = None
        self.topic_template = None  # Store the original topic template with variables
        self.topic = None  # Store the resolved topic
        self.port = 1883
        self.username = None
        self.password = None

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for MQTT destination"""
        base_schema = super().get_config_schema()
        
        mqtt_fields = [
            {
                'name': 'server',
                'label': 'MQTT Server',
                'type': 'text',
                'placeholder': 'e.g., localhost or 192.168.1.100',
                'description': 'MQTT broker hostname or IP address',
                'required': True
            },
            {
                'name': 'port',
                'label': 'Port',
                'type': 'number',
                'min': 1,
                'max': 65535,
                'placeholder': '1883',
                'description': 'MQTT broker port',
                'required': True,
                'default': 1883
            },
            {
                'name': 'topic',
                'label': 'Topic',
                'type': 'text',
                'placeholder': 'e.g., inference/results/{pipeline_id}',
                'description': 'MQTT topic (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': True
            },
            {
                'name': 'username',
                'label': 'Username',
                'type': 'text',
                'placeholder': 'Optional MQTT username',
                'description': 'Username for MQTT authentication',
                'required': False
            },
            {
                'name': 'password',
                'label': 'Password',
                'type': 'password',
                'placeholder': 'Optional MQTT password',
                'description': 'Password for MQTT authentication',
                'required': False
            }
        ]
        
        # Add MQTT-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(mqtt_fields)
        return base_schema
    
    def configure(self, server: str, topic: str, port: int = 1883, 
                 username: Optional[str] = None, password: Optional[str] = None,
                 rate_limit: Optional[float] = None, max_frames: Optional[int] = None,
                 include_image_data: bool = False, include_result_image: bool = False) -> None:
        """Configure MQTT destination"""
        try:
            import paho.mqtt.client as mqtt
            
            # Configure common parameters
            self.configure_common(rate_limit=rate_limit, max_frames=max_frames, 
                                include_image_data=include_image_data, include_result_image=include_result_image)
            
            # Configure MQTT-specific parameters
            self.server = server
            self.topic_template = topic  # Store original template
            self.topic = topic  # Will be resolved during publish
            self.port = port
            self.username = username
            self.password = password
            
            # Create MQTT client
            self.client = mqtt.Client()
            
            if username and password:
                self.client.username_pw_set(username, password)
            
            # Set a shorter timeout for connection attempts
            self.client.connect(server, port, 10)  # 10 second timeout instead of 60
            self.client.loop_start()
            
            self.is_configured = True
            self.logger.info(f"MQTT configured: {server}:{port}/{topic}")
            
        except ImportError:
            self.logger.error("paho-mqtt package not installed. Install with: pip install paho-mqtt")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
        except Exception as e:
            self.logger.error(f"MQTT configuration failed: {str(e)}")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Publish to MQTT topic"""
        try:
            # Check if client is configured and available
            if not self.client:
                # Don't log error here - let base class handle it with failure tracking
                return False
                
            # Add timestamp
            data["timestamp"] = datetime.utcnow().isoformat()
            
            # Resolve topic with variable substitution
            # Extract additional variables from data for substitution
            additional_vars = {}
            if 'pipeline_id' in data:
                additional_vars['pipeline_id'] = data['pipeline_id']
            if 'model_name' in data:
                additional_vars['model_name'] = data['model_name']
            
            # Debug: log available variables if debug logging is enabled
            if self.logger.isEnabledFor(logging.DEBUG):
                available_vars = self.get_available_variables(additional_vars)
                self.logger.debug(f"MQTT substitution - Template: {self.topic_template}")
                self.logger.debug(f"MQTT substitution - Available variables: {available_vars}")
            
            resolved_topic = self.substitute_variables(self.topic_template or '', additional_vars)
            
            message = json.dumps(data)
            result = self.client.publish(resolved_topic, message)
            
            if result.rc == 0:
                self.logger.debug(f"Published to MQTT: {resolved_topic}")
                return True
            else:
                # Don't log error here - let base class handle it with failure tracking
                return False
                
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False

    def close(self) -> None:
        """Close the MQTT connection"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.logger.info(f"MQTT connection closed: {self.server}:{self.port}/{self.topic}")