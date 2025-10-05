import json
import time
import base64
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path

try:
    from ..base_destination import BaseResultDestination
except ImportError:
    # Fallback for when running directly
    from base_destination import BaseResultDestination

class FolderDestination(BaseResultDestination):
    """Folder/File result destination"""
    
    def __init__(self):
        super().__init__()
        self.folder_path_template = None  # Store the original folder path template with variables
        self.folder_path = None
        self.file_prefix_template = None  # Store the original file prefix template with variables
        self.file_prefix = "inference_"
        self.file_extension = ".json"
        self.image_extension = ".jpg"

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for Folder destination"""
        base_schema = super().get_config_schema()
        
        folder_fields = [
            {
                'name': 'folder_path',
                'label': 'Folder Path',
                'type': 'text',
                'placeholder': 'e.g., ./output/{pipeline_id} or C:\\results',
                'description': 'Output folder path (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': True
            },
            {
                'name': 'file_prefix',
                'label': 'File Prefix',
                'type': 'text',
                'placeholder': 'inference_',
                'description': 'Prefix for output files (supports variables: {pipeline_id}, {model_name}, {node_id})',
                'required': False,
                'default': 'inference_'
            },
            {
                'name': 'file_extension',
                'label': 'File Extension',
                'type': 'select',
                'options': [
                    {'value': '.json', 'label': 'JSON (.json)'},
                    {'value': '.txt', 'label': 'Text (.txt)'},
                    {'value': '.csv', 'label': 'CSV (.csv)'}
                ],
                'description': 'File format for output files',
                'required': False,
                'default': '.json'
            }
        ]
        
        # Add folder-specific fields to base schema (which already has common fields)
        base_schema['fields'].extend(folder_fields)

        # Override the description for include_image_data to be more specific for Geti
        for field in base_schema['fields']:
            if field['name'] == 'include_image_data':
                field['default'] = True  # enable image data by default
            if field['name'] == 'include_result_image':
                field['default'] = True  # enable result image by default


        return base_schema
    
    def configure(self, folder_path: str, file_prefix: str = "inference_", 
                 file_extension: str = ".json", rate_limit: Optional[float] = None,
                 max_frames: Optional[int] = None,
                 include_image_data: bool = False,
                 include_result_image: bool = False) -> None:
        """Configure folder destination"""
        import os
        
        # Configure common parameters
        self.configure_common(rate_limit=rate_limit, max_frames=max_frames,
                            include_image_data=include_image_data, include_result_image=include_result_image)
        
        # Configure folder-specific parameters
        self.folder_path_template = folder_path  # Store original template
        self.folder_path = folder_path
        self.file_prefix_template = file_prefix  # Store original template
        self.file_prefix = file_prefix
        self.file_extension = file_extension if file_extension.startswith('.') else f".{file_extension}"
        
        # Ensure folder exists
        try:
            resolved_folder = self.substitute_variables(self.folder_path_template or '')
            resolved_folder = os.path.normpath(resolved_folder)
            resolved_folder = str(Path(resolved_folder).resolve())
            os.makedirs(resolved_folder, exist_ok=True)
            self.is_configured = True
            self.logger.info(f"Folder configured: {resolved_folder}")
        except Exception as e:
            self.logger.error(f"Failed to create folder '{folder_path}': {str(e)}")
            self.is_configured = False
    
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Publish to folder as a JSON file"""
        import os
        
        try:
            # Resolve folder path and file prefix with variable substitution
            additional_vars = {}
            if 'pipeline_id' in data:
                additional_vars['pipeline_id'] = data['pipeline_id']
            if 'model_name' in data:
                additional_vars['model_name'] = data['model_name']
            
            resolved_folder = self.substitute_variables(self.folder_path_template or '', additional_vars)
            resolved_prefix = self.substitute_variables(self.file_prefix_template or '', additional_vars)
            
            # Ensure folder exists
            os.makedirs(resolved_folder, exist_ok=True)
            
            # Create unique filename with timestamp and random component to avoid collisions
            timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%S')
            unique_id = int(time.time() * 1000)  # Millisecond precision
            base_filename = f"{resolved_prefix}{timestamp}_{unique_id}"
            json_filename = f"{base_filename}{self.file_extension}"
            json_file_path = os.path.join(resolved_folder, json_filename)

            # Check if data contains base64 image and save it separately
            image_saved = False
            json_data = data.copy()  # Create a copy to avoid modifying original data
            
            if 'image' in data and data['image']:
                try:
                    # Decode base64 image data
                    image_data = base64.b64decode(data['image'])
                    
                    # Create image filename with same base name as JSON
                    image_filename = f"{base_filename}{self.image_extension}"
                    image_file_path = os.path.join(resolved_folder, image_filename)
                    
                    # Save image file
                    with open(image_file_path, 'wb') as img_f:
                        img_f.write(image_data)
                    
                    image_saved = True
                    self.logger.debug(f"Saved image to: {image_file_path}")
                    
                    # Remove image data from JSON to avoid storing large base64 string
                    json_data.pop('image', None)
                    
                except Exception as img_e:
                    self.logger.warning(f"Failed to save image data: {str(img_e)}")
                    # Continue with JSON save even if image save fails

            if 'result_image' in data and data['result_image']:
                try:
                    # Decode base64 result image data
                    result_image_data = base64.b64decode(data['result_image'])
                    
                    # Create result image filename with same base name as JSON
                    result_image_filename = f"{base_filename}_result{self.image_extension}"
                    result_image_file_path = os.path.join(resolved_folder, result_image_filename)
                    
                    # Save result image file
                    with open(result_image_file_path, 'wb') as res_img_f:
                        res_img_f.write(result_image_data)
                    
                    image_saved = True
                    self.logger.debug(f"Saved result image to: {result_image_file_path}")
                    
                    # Remove result image data from JSON to avoid storing large base64 string
                    json_data.pop('result_image', None)
                    
                except Exception as res_img_e:
                    self.logger.warning(f"Failed to save result image data: {str(res_img_e)}")
                    # Continue with JSON save even if result image save fails

            # Write data to file (without image data if it was saved separately)
            with open(json_file_path, 'w') as f:
                json.dump(json_data, f)
            
            if image_saved:
                self.logger.debug(f"Published to folder: {json_file_path} (with image)")
            else:
                self.logger.debug(f"Published to folder: {json_file_path}")
            return True

        except Exception as e:
            # Don't log error here - let base class handle it with failure tracking
            return False

    def close(self):
        """Close folder destination"""
        pass