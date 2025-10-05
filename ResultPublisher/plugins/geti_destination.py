# import json
import base64
# import io
from typing import Any, Dict, Optional
# from datetime import datetime
# import tempfile
# import os
# import numpy as np


try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination


class GetiDestination(BaseResultDestination):
    """Geti result destination for uploading images to Geti platform"""
    
    def __init__(self):
        super().__init__()
        self.host = None
        self.token = None
        self.project_name = None
        self.project_id = None
        self.dataset_name = None
        self.verify_certificate = True
        self.geti_client = None
        self.project = None
        self.image_client = None
        
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get the configuration schema for Geti destination"""
        base_schema = super().get_config_schema()
        
        geti_fields = [
            {
                'name': 'host',
                'label': 'Geti Server Host',
                'type': 'text',
                'required': True,
                'placeholder': 'https://your_geti_server.com',
                'description': 'URL or IP address of the Geti server'
            },
            {
                'name': 'token',
                'label': 'Personal Access Token',
                'type': 'password',
                'required': True,
                'placeholder': 'Your Geti personal access token',
                'description': 'Personal access token from Geti user menu'
            },
            {
                'name': 'project_name',
                'label': 'Project Name',
                'type': 'text',
                'required': False,
                'placeholder': 'e.g., my-detection-project',
                'description': 'Name of the Geti project (either project_name or project_id required)'
            },
            {
                'name': 'project_id',
                'label': 'Project ID',
                'type': 'text',
                'required': False,
                'placeholder': 'e.g., 12345678-1234-1234-1234-123456789abc',
                'description': 'UUID of the Geti project (either project_name or project_id required)'
            },
            {
                'name': 'dataset_name',
                'label': 'Dataset Name',
                'type': 'text',
                'required': False,
                'placeholder': 'e.g., inference-data',
                'description': 'Name of the dataset within the project (optional, uses training dataset if not specified)'
            },
            {
                'name': 'verify_certificate',
                'label': 'Verify SSL Certificate',
                'type': 'checkbox',
                'default': False,
                'description': 'Verify SSL certificates for HTTPS connections'
            }
        ]
        
        # Add geti-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(geti_fields)
        
        # Override the description for include_image_data to be more specific for Geti
        for field in base_schema['fields']:
            if field['name'] == 'include_image_data':
                field['description'] = 'Must be enabled to upload images to Geti'
                field['default'] = True  # Geti needs images by default
        
        return base_schema
    
    def configure(self, host: str, token: str,
                 project_name: Optional[str] = None, project_id: Optional[str] = None,
                 dataset_name: Optional[str] = None, verify_certificate: bool = False,
                 rate_limit: Optional[float] = None, max_frames: Optional[int] = None,
                 include_image_data: bool = True, include_result_image: bool = False) -> None:
        """Configure Geti destination"""
        try:
            from geti_sdk import Geti
            from geti_sdk.rest_clients import ProjectClient, ImageClient, DatasetClient
            import cv2
            
            # Configure common parameters
            self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                                include_image_data=include_image_data, include_result_image=include_result_image)
            
            # Configure Geti-specific parameters
            self.host = host
            self.token = token
            self.project_name = project_name
            self.project_id = project_id
            self.dataset_name = dataset_name
            self.verify_certificate = verify_certificate
            
            if not include_image_data:
                self.logger.warning("include_image_data is False - Geti uploads require image data")
            
            if not project_name and not project_id:
                raise ValueError("Either project_name or project_id must be specified")
            
            # Initialize Geti client
            self.geti_client = Geti(
                host=host,
                token=token,
                verify_certificate=verify_certificate
            )
            
            # Get or create project
            project_client = ProjectClient(
                session=self.geti_client.session,
                workspace_id=self.geti_client.workspace_id
            )
            
            if project_name:
                try:
                    self.project = project_client.get_project_by_name(project_name)
                    self.logger.info(f"Found existing project: {project_name}")
                except Exception as e:
                    self.logger.error(f"Project '{project_name}' not found: {str(e)}")
                    self.is_configured = False
                    return
            elif project_id:
                try:
                    self.project = project_client.get_project_by_id(project_id)
                    self.logger.info(f"Found project with ID: {project_id}")
                except Exception as e:
                    self.logger.error(f"Project with ID '{project_id}' not found: {str(e)}")
                    self.is_configured = False
                    return
            
            # Initialize image client - only if project was found
            if self.project is None:
                self.logger.error("No project found, cannot initialize image client")
                self.is_configured = False
                return
                
            self.image_client = ImageClient(
                session=self.geti_client.session,
                workspace_id=self.geti_client.workspace_id,
                project=self.project
            )
            
            # Get dataset if specified
            self.dataset = None
            if dataset_name:
                try:
                    dataset_client = DatasetClient(
                        session=self.geti_client.session,
                        workspace_id=self.geti_client.workspace_id,
                        project=self.project
                    )
                    self.dataset = dataset_client.get_dataset_by_name(dataset_name)
                    self.logger.info(f"Using dataset: {dataset_name}")
                except Exception as e:
                    self.logger.warning(f"Dataset '{dataset_name}' not found, using training dataset: {str(e)}")
                    self.dataset = None
            
            self.is_configured = True
            project_identifier = self.project.name if hasattr(self.project, 'name') and self.project.name else str(self.project.id)
            self.logger.info(f"Geti configured: {host} -> {project_identifier}")
            
        except ImportError:
            self.logger.error("geti-sdk package not installed. Install with: pip install geti-sdk")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
        except Exception as e:
            self.logger.error(f"Geti configuration failed: {str(e)}")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Upload image data to Geti platform"""
        try:
            # Check if clients are configured and available
            if not self.image_client or not self.project:
                return False
                
            # Check if image data is available
            if 'image' not in data or not data['image']:
                self.logger.warning("No image data found in result - skipping Geti upload")
                return False
                
            # Decode base64 image data
            try:
                image_data = base64.b64decode(data['image'])
            except Exception as e:
                self.logger.error(f"Failed to decode base64 image data: {str(e)}")
                return False
            
            # Convert bytes to numpy array for Geti SDK
            try:
                import cv2
                import numpy as np
                
                # Convert bytes to numpy array
                nparr = np.frombuffer(image_data, np.uint8)
                image_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if image_array is None:
                    self.logger.error("Failed to decode image data to numpy array")
                    return False
                
            except Exception as e:
                self.logger.error(f"Failed to convert image data to numpy array: {str(e)}")
                return False
            
            # Upload image to Geti
            try:
                uploaded_image = self.image_client.upload_image(
                    image=image_array,
                    dataset=self.dataset
                )
                
                project_identifier = self.project.name if self.project.name else self.project.id
                self.logger.debug(f"Uploaded image to Geti project: {project_identifier}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to upload image to Geti: {str(e)}")
                return False
            
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False
    
    def close(self) -> None:
        """Close the Geti connection"""
        if self.geti_client:
            try:
                self.geti_client.logout()
            except Exception as e:
                self.logger.warning(f"Error during Geti logout: {str(e)}")
            finally:
                project_identifier = self.project_name or self.project_id or "unknown"
                self.geti_client = None
                self.image_client = None
                self.project = None
                self.logger.info(f"Geti connection closed: {self.host} -> {project_identifier}")

if __name__ == "__main__":
    # Example usage
    destination = GetiDestination()
    destination.configure(
        host="https://your_geti_server.com",
        token="your_personal_access_token",
        project_name="my-detection-project"
    )

    import cv2
    image = cv2.imread("C:\\Users\\olive\\OneDrive\\Projects\\InferNode\\test_image\\test.jpg")
    if image is not None:
        _, buffer = cv2.imencode('.jpg', image)
        jpg_as_text = base64.b64encode(buffer.tobytes()).decode('utf-8')

        data = {
            "image": jpg_as_text
        }
        destination.publish(data)

    # Close the connection
    destination.close()