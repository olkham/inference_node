import json
from typing import Any, Dict, Optional
from datetime import datetime
try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination

class ROS2Destination(BaseResultDestination):
    """ROS2 result destination"""
    
    def __init__(self):
        super().__init__()
        self.node = None
        self.publisher = None
        self.topic_template = None  # Store the original topic template with variables
        self.topic = None
        self.message_type = "std_msgs/String"  # Default message type
        self.qos_profile = None
        self.node_name = "inference_publisher"
        self._rclpy_initialized = False

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for ROS2 destination"""
        base_schema = super().get_config_schema()
        
        ros2_fields = [
            {
                'name': 'topic',
                'label': 'ROS2 Topic',
                'type': 'text',
                'placeholder': 'e.g., /inference/results/{pipeline_id}',
                'description': 'ROS2 topic name (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': True
            },
            {
                'name': 'message_type',
                'label': 'Message Type',
                'type': 'select',
                'options': [
                    {'value': 'std_msgs/String', 'label': 'std_msgs/String (JSON as string)'},
                    {'value': 'sensor_msgs/Image', 'label': 'sensor_msgs/Image (with image data)'},
                    {'value': 'geometry_msgs/Point', 'label': 'geometry_msgs/Point (detection points)'}
                ],
                'description': 'ROS2 message type for publishing',
                'required': False,
                'default': 'std_msgs/String'
            },
            {
                'name': 'node_name',
                'label': 'Node Name',
                'type': 'text',
                'placeholder': 'inference_publisher',
                'description': 'ROS2 node name (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': False,
                'default': 'inference_publisher'
            },
            {
                'name': 'qos_profile',
                'label': 'QoS Profile',
                'type': 'select',
                'options': [
                    {'value': '', 'label': 'Default'},
                    {'value': 'sensor_data', 'label': 'Sensor Data (best effort)'},
                    {'value': 'reliable', 'label': 'Reliable (guaranteed delivery)'}
                ],
                'description': 'Quality of Service profile for message delivery',
                'required': False
            }
        ]
        
        # Add ROS2-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(ros2_fields)
        return base_schema
    
    def configure(self, topic: str, message_type: str = "std_msgs/String", 
                 node_name: str = "inference_publisher", qos_profile: Optional[str] = None,
                 rate_limit: Optional[float] = None, max_frames: Optional[int] = None,
                 include_image_data: bool = False, include_result_image: bool = False) -> None:
        """Configure ROS2 destination"""
        try:
            import rclpy
            from rclpy.node import Node
            from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
            from std_msgs.msg import String
            
            # Configure common parameters
            self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                                include_image_data=include_image_data, include_result_image=include_result_image)
            
            # Configure ROS2-specific parameters
            self.topic_template = topic  # Store original template
            self.topic = topic
            self.message_type = message_type
            self.node_name = node_name
            
            # Initialize rclpy if not already done
            if not rclpy.ok():
                rclpy.init()
                self._rclpy_initialized = True
            
            # Create ROS2 node
            self.node = Node(node_name)
            
            # Configure QoS profile
            if qos_profile == "sensor_data":
                qos = QoSProfile(
                    reliability=ReliabilityPolicy.BEST_EFFORT,
                    durability=DurabilityPolicy.VOLATILE,
                    depth=10
                )
            elif qos_profile == "reliable":
                qos = QoSProfile(
                    reliability=ReliabilityPolicy.RELIABLE,
                    durability=DurabilityPolicy.TRANSIENT_LOCAL,
                    depth=10
                )
            else:
                qos = 10  # Default QoS depth
            
            self.qos_profile = qos
            
            # Determine message type and create publisher
            if message_type == "std_msgs/String":
                self.publisher = self.node.create_publisher(String, topic, qos)
            else:
                # For other message types, we'll try to import them dynamically
                # This is a simplified approach - in practice you might want more robust message type handling
                self.logger.warning(f"Message type {message_type} not fully supported, falling back to std_msgs/String")
                self.publisher = self.node.create_publisher(String, topic, qos)
            
            self.is_configured = True
            self.logger.info(f"ROS2 configured: {topic} ({message_type}) on node {node_name}")
            
        except ImportError:
            self.logger.error("rclpy package not installed. Install ROS2 and rclpy: pip install rclpy")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
        except Exception as e:
            self.logger.error(f"ROS2 configuration failed: {str(e)}")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Publish to ROS2 topic"""
        try:
            import rclpy
            from std_msgs.msg import String
            
            # Check if node and publisher are configured and available
            if not self.node or not self.publisher:
                # Don't log error here - let base class handle it with failure tracking
                return False
                
            # Add timestamp
            data["timestamp"] = datetime.utcnow().isoformat()
            
            # Resolve topic with variable substitution
            additional_vars = {}
            if 'pipeline_id' in data:
                additional_vars['pipeline_id'] = data['pipeline_id']
            if 'model_name' in data:
                additional_vars['model_name'] = data['model_name']
            
            resolved_topic = self.substitute_variables(self.topic_template or '', additional_vars)
            
            # Convert data to JSON string for ROS2 message
            message_data = json.dumps(data)
            
            # Create and publish message
            if self.message_type == "std_msgs/String":
                msg = String()
                msg.data = message_data
                self.publisher.publish(msg)
            else:
                # For other message types, fall back to String
                msg = String()
                msg.data = message_data
                self.publisher.publish(msg)
            
            # Spin once to process any callbacks
            rclpy.spin_once(self.node, timeout_sec=0.1)
            
            self.logger.debug(f"Published to ROS2: {resolved_topic}")
            return True
                
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False

    def close(self) -> None:
        """Close the ROS2 connection"""
        try:
            import rclpy
            
            if self.node:
                # Destroy the publisher
                if self.publisher:
                    self.node.destroy_publisher(self.publisher)
                    self.publisher = None
                
                # Destroy the node
                self.node.destroy_node()
                self.node = None
                
                self.logger.info(f"ROS2 node destroyed: {self.node_name}")
            
            # Shutdown rclpy if we initialized it
            if self._rclpy_initialized and rclpy.ok():
                rclpy.shutdown()
                self._rclpy_initialized = False
                self.logger.info("ROS2 rclpy shutdown")
                
        except Exception as e:
            self.logger.debug(f"Error during ROS2 cleanup: {str(e)}")