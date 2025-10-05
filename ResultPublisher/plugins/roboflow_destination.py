import json
import base64
import io
from typing import Any, Dict, Optional
from datetime import datetime
import tempfile
import os


try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination


class RoboflowDestination(BaseResultDestination):
    """Roboflow result destination for uploading images to Roboflow workspace"""
    
    def __init__(self):
        super().__init__()
        self.api_key = None
        self.workspace_id = None
        self.project_id = None
        self.dataset_name = None
        self.split = "train"  # Default split: train, valid, or test
        self.upload_batch_name = "From InferNode"
        self.roboflow_project = None
        
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get the configuration schema for Roboflow destination"""
        base_schema = super().get_config_schema()
        
        roboflow_fields = [
            {
                'name': 'api_key',
                'label': 'Roboflow API Key',
                'type': 'password',
                'required': True,
                'placeholder': 'Your Roboflow API key',
                'description': 'API key from Roboflow workspace settings'
            },
            {
                'name': 'workspace_id',
                'label': 'Workspace ID',
                'type': 'text',
                'required': True,
                'placeholder': 'e.g., my-workspace',
                'description': 'Roboflow workspace identifier'
            },
            {
                'name': 'project_id',
                'label': 'Project ID',
                'type': 'text',
                'required': True,
                'placeholder': 'e.g., my-project',
                'description': 'Roboflow project identifier'
            },
            {
                'name': 'dataset_name',
                'label': 'Dataset Name',
                'type': 'text',
                'required': False,
                'placeholder': 'e.g., inference-batch-{date}',
                'description': 'Name for the dataset batch (supports variable substitution)'
            },
            {
                'name': 'split',
                'label': 'Dataset Split',
                'type': 'select',
                'options': [
                    {'value': 'train', 'label': 'Train'},
                    {'value': 'valid', 'label': 'Validation'},
                    {'value': 'test', 'label': 'Test'}
                ],
                'default': 'train',
                'description': 'Which dataset split to upload images to'
            },
            {
                'name': 'upload_batch_name',
                'label': 'Upload Batch Name',
                'type': 'text',
                'required': False,
                'placeholder': 'e.g., batch-{timestamp}',
                'description': 'Name for the upload batch (supports variable substitution)'
            }
        ]
        
        # Add roboflow-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(roboflow_fields)
        
        # Override the description for include_image_data to be more specific for Roboflow
        for field in base_schema['fields']:
            if field['name'] == 'include_image_data':
                field['description'] = 'Must be enabled to upload images to Roboflow'
                field['default'] = True  # Roboflow needs images by default
        
        return base_schema
    
    def configure(self, api_key: str, workspace_id: str, project_id: str,
                 dataset_name: Optional[str] = None, split: str = "train",
                 upload_batch_name: Optional[str] = None,
                 rate_limit: Optional[float] = None, max_frames: Optional[int] = None,
                 include_image_data: bool = True, include_result_image: bool = False) -> None:
        """Configure Roboflow destination"""
        try:
            from roboflow import Roboflow
            
            # Configure common parameters
            self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                                include_image_data=include_image_data, include_result_image=include_result_image)
            
            # Configure Roboflow-specific parameters
            self.api_key = api_key
            self.workspace_id = workspace_id
            self.project_id = project_id
            self.dataset_name = dataset_name or f"inference-batch-{datetime.utcnow().strftime('%Y%m%d')}"
            self.split = split
            self.upload_batch_name = upload_batch_name
            
            if not include_image_data:
                self.logger.warning("include_image_data is False - Roboflow uploads require image data")
            
            # Initialize Roboflow client
            rf = Roboflow(api_key=api_key)
            
            # Get the workspace and project
            workspace = rf.workspace(workspace_id)
            self.roboflow_project = workspace.project(project_id)
            
            self.is_configured = True
            self.logger.info(f"Roboflow configured: {workspace_id}/{project_id}")
            
        except ImportError:
            self.logger.error("roboflow package not installed. Install with: pip install roboflow")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
        except Exception as e:
            self.logger.error(f"Roboflow configuration failed: {str(e)}")
            self.is_configured = False
            # Don't raise - allow pipeline to continue without this destination
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Upload image data to Roboflow"""
        try:
            # Check if project is configured and available
            if not self.roboflow_project:
                return False
                
            # Check if image data is available
            if 'image' not in data or not data['image']:
                self.logger.warning("No image data found in result - skipping Roboflow upload")
                return False
                
            # Decode base64 image data
            try:
                image_data = base64.b64decode(data['image'])
            except Exception as e:
                self.logger.error(f"Failed to decode base64 image data: {str(e)}")
                return False
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # millisecond precision
            filename = f"inference_{timestamp}.jpg"
            
            # Write image data to a temporary file
            temp_dir = tempfile.gettempdir()
            temp_image_path = os.path.join(temp_dir, filename)
            
            try:
                with open(temp_image_path, 'wb') as f:
                    f.write(image_data)
                
                # Simple upload using basic method
                self.roboflow_project.upload(temp_image_path,
                                             batch_name=self.upload_batch_name)

                self.logger.debug(f"Uploaded to Roboflow: {self.workspace_id}/{self.project_id}")
                return True
                
            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)
                except Exception as cleanup_error:
                    self.logger.warning(f"Failed to cleanup temporary file: {cleanup_error}")
            
        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False
    
    # def _format_annotations(self, annotations: list, data: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     Format annotation data for Roboflow upload.
    #     This is a basic implementation - you may need to customize based on your annotation format.
    #     """
    #     try:
    #         # Get image dimensions if available
    #         image_width = data.get('image_width', 640)
    #         image_height = data.get('image_height', 480)
            
    #         formatted_annotations = []
            
    #         for annotation in annotations:
    #             if isinstance(annotation, dict):
    #                 # Extract bounding box and class information
    #                 bbox = annotation.get('bbox', annotation.get('bounding_box'))
    #                 class_name = annotation.get('class', annotation.get('label', annotation.get('class_name')))
    #                 confidence = annotation.get('confidence', annotation.get('score', 1.0))
                    
    #                 if bbox and class_name:
    #                     # Convert to Roboflow format (normalized coordinates)
    #                     if len(bbox) >= 4:
    #                         x, y, w, h = bbox[:4]
                            
    #                         # Normalize coordinates if they appear to be in pixel values
    #                         if x > 1 or y > 1 or w > 1 or h > 1:
    #                             x = x / image_width
    #                             y = y / image_height
    #                             w = w / image_width
    #                             h = h / image_height
                            
    #                         formatted_annotation = {
    #                             'class': str(class_name),
    #                             'x': float(x + w/2),  # Center x
    #                             'y': float(y + h/2),  # Center y
    #                             'width': float(w),
    #                             'height': float(h),
    #                             'confidence': float(confidence)
    #                         }
    #                         formatted_annotations.append(formatted_annotation)
            
    #         return {
    #             'annotations': formatted_annotations,
    #             'image_width': image_width,
    #             'image_height': image_height
    #         }
            
    #     except Exception as e:
    #         self.logger.warning(f"Failed to format annotations: {str(e)}")
    #         return {}

    def close(self) -> None:
        """Close the Roboflow connection"""
        if self.roboflow_project:
            self.roboflow_project = None
            self.logger.info(f"Roboflow connection closed: {self.workspace_id}/{self.project_id}")

if __name__ == "__main__":
    # Example usage
    destination = RoboflowDestination()
    destination.configure(
        api_key="JdE7CKe7XqlZsvd7EJcx",
        workspace_id="oliver-be5uk",
        project_id="slugs-f0qfr"
    )

    import cv2
    image = cv2.imread("C:\\Users\\olive\\OneDrive\\Projects\\InferNode\\test_image\\test.jpg")
    _, buffer = cv2.imencode('.jpg', image)
    jpg_as_text = base64.b64encode(buffer.tobytes()).decode('utf-8')

    data = {
        "image": jpg_as_text
    }
    destination.publish(data)

    # You can now use destination.publish(data) to upload results
    destination.close()