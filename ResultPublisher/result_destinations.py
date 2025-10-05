# This file is maintained for backward compatibility
# All destination classes have been moved to their own separate files

# Import all destination classes from their new locations
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

# Export all classes for backward compatibility
__all__ = [
    'BaseResultDestination',
    'NullDestination',
    'MQTTDestination',
    'WebhookDestination',
    'SerialDestination',
    'FolderDestination',
    'ZeroMQDestination',
    'OPCUADestination',
    'ROS2Destination',
    'RoboflowDestination',
    'GetiDestination'
]