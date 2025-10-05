import json
from typing import Any, Dict, Optional
from datetime import datetime
try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination

class SerialDestination(BaseResultDestination):
    """Serial port result destination"""
    
    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.com_port = None
        self.baud_rate = 9600

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for Serial destination"""
        base_schema = super().get_config_schema()
        
        serial_fields = [
            {
                'name': 'com_port',
                'label': 'COM Port',
                'type': 'text',
                'placeholder': 'e.g., COM1, COM3, /dev/ttyUSB0',
                'description': 'Serial port identifier (Windows: COM1, COM2... Linux: /dev/ttyUSB0, /dev/ttyACM0...)',
                'required': True
            },
            {
                'name': 'baud_rate',
                'label': 'Baud Rate',
                'type': 'select',
                'options': [
                    {'value': 9600, 'label': '9600'},
                    {'value': 19200, 'label': '19200'},
                    {'value': 38400, 'label': '38400'},
                    {'value': 57600, 'label': '57600'},
                    {'value': 115200, 'label': '115200'}
                ],
                'description': 'Serial communication speed',
                'required': False,
                'default': 9600
            }
        ]
        
        # Add serial-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(serial_fields)
        return base_schema
    
    def configure(self, com_port: str, baud: int = 9600, 
                 rate_limit: Optional[float] = None, max_frames: Optional[int] = None,
                 include_image_data: bool = False, include_result_image: bool = False) -> None:
        """Configure serial destination"""
        try:
            import serial
            
            # Configure common parameters
            self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                                include_image_data=include_image_data, include_result_image=include_result_image)
            
            # Configure serial-specific parameters
            self.com_port = com_port
            self.baud_rate = baud
            
            self.serial_port = serial.Serial(com_port, baud, timeout=1)
            
            self.is_configured = True
            self.logger.info(f"Serial configured: {com_port} @ {baud} baud")
            
        except ImportError:
            self.logger.error("pyserial package not installed. Install with: pip install pyserial")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
        except Exception as e:
            self.logger.error(f"Serial configuration failed: {str(e)}")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Publish to serial port"""
        try:
            # Check if serial port is configured and available
            if not self.serial_port or not self.serial_port.is_open:
                # Don't log error here - let base class handle it with failure tracking
                return False
                
            # Add timestamp
            data["timestamp"] = datetime.utcnow().isoformat()
            
            message = json.dumps(data) + "\n"
            self.serial_port.write(message.encode('utf-8'))
            self.serial_port.flush()
            
            self.logger.debug(f"Published to serial: {self.com_port}")
            return True
            
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False
    
    def close(self):
        """Close serial connection"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()