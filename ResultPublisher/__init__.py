# Import all destination classes from their individual modules
from .base_destination import BaseResultDestination
from .plugins.null_destination import NullDestination
from .plugins.mqtt_destination import MQTTDestination
from .plugins.webhook_destination import WebhookDestination
from .plugins.serial_destination import SerialDestination
from .plugins.folder_destination import FolderDestination
from .plugins.zeromq_destination import ZeroMQDestination
from .plugins.opcua_destination import OPCUADestination
from .plugins.ros2_destination import ROS2Destination
from .plugins.roboflow_destination import RoboflowDestination
from .plugins.geti_destination import GetiDestination
from .publisher import ResultPublisher

def ResultDestination(destination_type: str):
    """Factory function to create result destinations"""
    destinations = {
        'mqtt': MQTTDestination,
        'webhook': WebhookDestination,
        'serial': SerialDestination,
        'file': FolderDestination,
        'folder': FolderDestination,
        'zmq': ZeroMQDestination,
        'zeromq': ZeroMQDestination,
        'opcua': OPCUADestination,
        'opc-ua': OPCUADestination,
        'ros2': ROS2Destination,
        'ros': ROS2Destination,
        'roboflow': RoboflowDestination,
        'geti': GetiDestination,
        'null': NullDestination
    }
    
    if destination_type not in destinations:
        raise ValueError(f"Unsupported destination type: {destination_type}. Available: {list(destinations.keys())}")
    
    return destinations[destination_type]()

def get_available_destination_types():
    """Get list of available destination types with metadata"""
    destination_metadata = [
        {
            'type': 'mqtt',
            'name': 'MQTT',
            'description': 'Publish results to an MQTT broker',
            'icon': 'fas fa-broadcast-tower',
            'class': MQTTDestination,
            'primary': True
        },
        {
            'type': 'webhook',
            'name': 'Webhook',
            'description': 'Send HTTP POST requests to a web endpoint',
            'icon': 'fas fa-globe',
            'class': WebhookDestination,
            'primary': True
        },
        {
            'type': 'serial',
            'name': 'Serial Port',
            'description': 'Send data over a serial connection',
            'icon': 'fas fa-plug',
            'class': SerialDestination,
            'primary': True
        },
        {
            'type': 'folder',
            'name': 'File/Folder',
            'description': 'Save results to files in a directory',
            'icon': 'fas fa-folder',
            'class': FolderDestination,
            'primary': True
        },
        {
            'type': 'zeromq',
            'name': 'ZeroMQ',
            'description': 'Publish via ZeroMQ messaging',
            'icon': 'fas fa-exchange-alt',
            'class': ZeroMQDestination,
            'primary': False
        },
        {
            'type': 'opcua',
            'name': 'OPC-UA',
            'description': 'Publish to OPC-UA server',
            'icon': 'fas fa-industry',
            'class': OPCUADestination,
            'primary': False
        },
        {
            'type': 'ros2',
            'name': 'ROS2',
            'description': 'Publish to ROS2 topics',
            'icon': 'fas fa-robot',
            'class': ROS2Destination,
            'primary': False
        },
        {
            'type': 'roboflow',
            'name': 'Roboflow',
            'description': 'Upload images to Roboflow workspace',
            'icon': 'fas fa-cloud-upload-alt',
            'class': RoboflowDestination,
            'primary': True
        },
        {
            'type': 'geti',
            'name': 'Geti',
            'description': 'Upload images to Geti platform',
            'icon': 'fas fa-microchip',
            'class': GetiDestination,
            'primary': True
        },
        {
            'type': 'null',
            'name': 'Null (Discard)',
            'description': 'Discard all results (for testing)',
            'icon': 'fas fa-trash-alt',
            'class': NullDestination,
            'primary': False
        }
    ]
    
    # Filter out destinations where the class isn't available (import failed)
    available_destinations = []
    for dest in destination_metadata:
        try:
            # Try to instantiate the class to check if dependencies are available
            test_instance = dest['class']()
            
            # Get configuration schema from the class
            try:
                config_schema = dest['class'].get_config_schema()
            except Exception as e:
                config_schema = {
                    'fields': [],
                    'error': f"Schema error: {str(e)}"
                }
            
            available_destinations.append({
                'type': dest['type'],
                'name': dest['name'],
                'description': dest['description'],
                'icon': dest['icon'],
                'primary': dest['primary'],
                'available': True,
                'config_schema': config_schema
            })
        except Exception as e:
            # Include but mark as unavailable if dependencies are missing
            available_destinations.append({
                'type': dest['type'],
                'name': dest['name'],
                'description': dest['description'],
                'icon': dest['icon'],
                'primary': dest['primary'],
                'available': False,
                'error': str(e),
                'config_schema': {
                    'fields': [],
                    'error': f"Destination unavailable: {str(e)}"
                }
            })

    return available_destinations

__all__ = [
    'ResultDestination', 
    'ResultPublisher',
    'BaseResultDestination',
    'MQTTDestination',
    'WebhookDestination', 
    'SerialDestination',
    'FolderDestination',
    'ZeroMQDestination',
    'OPCUADestination',
    'ROS2Destination',
    'RoboflowDestination',
    'GetiDestination',
    'NullDestination',
    'get_available_destination_types'
]
