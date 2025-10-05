import json
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime
try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination

class OPCUADestination(BaseResultDestination):
    """OPC UA result destination"""
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.server_url_template = None  # Store the original server URL template with variables
        self.server_url = None
        self.node_id_template = None  # Store the original node ID template with variables
        self.node_id = None
        self.username = None
        self.password = None
        self.security_policy = None
        self.security_mode = None

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for OPC UA destination"""
        base_schema = super().get_config_schema()
        
        opcua_fields = [
            {
                'name': 'server_url',
                'label': 'OPC UA Server URL',
                'type': 'url',
                'placeholder': 'e.g., opc.tcp://localhost:4840',
                'description': 'OPC UA server endpoint URL',
                'required': True
            },
            {
                'name': 'node_id',
                'label': 'Node ID',
                'type': 'text',
                'placeholder': 'e.g., ns=2;s=InferenceResults or ns=3;i=1001',
                'description': 'OPC UA node identifier to write data to (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': True
            },
            {
                'name': 'username',
                'label': 'Username',
                'type': 'text',
                'placeholder': 'Optional OPC UA username',
                'description': 'Username for OPC UA authentication',
                'required': False
            },
            {
                'name': 'password',
                'label': 'Password',
                'type': 'password',
                'placeholder': 'Optional OPC UA password',
                'description': 'Password for OPC UA authentication',
                'required': False
            },
            {
                'name': 'security_policy',
                'label': 'Security Policy',
                'type': 'select',
                'options': [
                    {'value': '', 'label': 'None'},
                    {'value': 'Basic256Sha256', 'label': 'Basic256Sha256'},
                    {'value': 'Aes128_Sha256_RsaOaep', 'label': 'Aes128_Sha256_RsaOaep'},
                    {'value': 'Aes256_Sha256_RsaPss', 'label': 'Aes256_Sha256_RsaPss'}
                ],
                'description': 'OPC UA security policy',
                'required': False
            },
            {
                'name': 'security_mode',
                'label': 'Security Mode',
                'type': 'select',
                'options': [
                    {'value': '', 'label': 'None'},
                    {'value': 'Sign', 'label': 'Sign'},
                    {'value': 'SignAndEncrypt', 'label': 'Sign and Encrypt'}
                ],
                'description': 'OPC UA security mode',
                'required': False
            }
        ]
        
        # Add OPC UA-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(opcua_fields)
        return base_schema
    
    def configure(self, server_url: str, node_id: str, 
                 username: Optional[str] = None, password: Optional[str] = None,
                 security_policy: Optional[str] = None, security_mode: Optional[str] = None,
                 rate_limit: Optional[float] = None, max_frames: Optional[int] = None,
                 include_image_data: bool = False, include_result_image: bool = False) -> None:
        """Configure OPC UA destination"""
        try:
            import asyncua
            
            # Configure common parameters
            self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                                include_image_data=include_image_data, include_result_image=include_result_image)
            
            # Configure OPC UA-specific parameters
            self.server_url_template = server_url  # Store original template
            self.server_url = server_url
            self.node_id_template = node_id  # Store original template
            self.node_id = node_id
            self.username = username
            self.password = password
            self.security_policy = security_policy
            self.security_mode = security_mode
            
            # Create OPC UA client
            self.client = asyncua.Client(url=server_url)
            
            # Configure security if provided
            if username and password:
                self.client.set_user(username)
                self.client.set_password(password)
            
            if security_policy and security_mode:
                self.client.set_security_string(f"{security_policy},{security_mode}")
            
            self.is_configured = True
            self.logger.info(f"OPC UA configured: {server_url} -> {node_id}")
            
        except ImportError:
            self.logger.error("asyncua package not installed. Install with: pip install asyncua")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
        except Exception as e:
            self.logger.error(f"OPC UA configuration failed: {str(e)}")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Publish to OPC UA node"""
        try:
            import asyncua
            
            # Check if client is configured and available
            if not self.client:
                # Don't log error here - let base class handle it with failure tracking
                return False
                
            # Add timestamp
            data["timestamp"] = datetime.utcnow().isoformat()
            
            # Resolve server URL and node ID with variable substitution
            additional_vars = {}
            if 'pipeline_id' in data:
                additional_vars['pipeline_id'] = data['pipeline_id']
            if 'model_name' in data:
                additional_vars['model_name'] = data['model_name']
            
            resolved_server_url = self.substitute_variables(self.server_url_template or '', additional_vars)
            resolved_node_id = self.substitute_variables(self.node_id_template or '', additional_vars)
            
            # Convert data to JSON string for OPC UA
            message = json.dumps(data)
            
            # Use asyncio to run the async OPC UA operations
            async def write_to_opcua():
                try:
                    # Update client URL if it changed due to variable substitution
                    if resolved_server_url != self.server_url:
                        await self.client.disconnect()
                        self.client = asyncua.Client(url=resolved_server_url)
                        if self.username and self.password:
                            self.client.set_user(self.username)
                            self.client.set_password(self.password)
                        if self.security_policy and self.security_mode:
                            self.client.set_security_string(f"{self.security_policy},{self.security_mode}")
                    
                    # Connect if not already connected
                    if not self.client.session:
                        await self.client.connect()
                    
                    # Get the node and write the value
                    node = self.client.get_node(resolved_node_id)
                    await node.write_value(message)
                    
                    return True
                except Exception as e:
                    self.logger.debug(f"OPC UA write failed: {str(e)}")
                    return False
            
            # Run the async operation
            loop = None
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an event loop, we need to use a different approach
                    # This is a limitation when running async code from sync code
                    self.logger.warning("Cannot perform async OPC UA operation from within async context")
                    return False
                else:
                    result = loop.run_until_complete(write_to_opcua())
            except RuntimeError:
                # No event loop running, create a new one
                result = asyncio.run(write_to_opcua())
            
            if result:
                self.logger.debug(f"Published to OPC UA: {resolved_server_url} -> {resolved_node_id}")
                return True
            else:
                return False
                
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False

    def close(self) -> None:
        """Close the OPC UA connection"""
        if self.client:
            try:
                async def disconnect_client():
                    try:
                        if self.client.session:
                            await self.client.disconnect()
                    except Exception as e:
                        self.logger.debug(f"Error disconnecting OPC UA client: {str(e)}")
                
                # Try to disconnect gracefully
                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_running():
                        loop.run_until_complete(disconnect_client())
                except RuntimeError:
                    asyncio.run(disconnect_client())
                except Exception as e:
                    self.logger.debug(f"Could not disconnect OPC UA client: {str(e)}")
                
                self.logger.info(f"OPC UA connection closed: {self.server_url} -> {self.node_id}")
            except Exception as e:
                self.logger.debug(f"Error during OPC UA cleanup: {str(e)}")