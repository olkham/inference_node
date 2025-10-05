import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

class ModelRepository:
    """Manages storage and retrieval of uploaded models"""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.models_dir = os.path.join(repo_path, 'models')
        self.metadata_file = os.path.join(repo_path, 'models_metadata.json')
        
        # Create directories if they don't exist
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Load existing metadata or create empty dict
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load model metadata from file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Migration: Add name field to existing models that don't have it
                needs_save = False
                for model_id, model_data in metadata.items():
                    if isinstance(model_data, dict) and 'name' not in model_data:
                        # Use original_filename without extension as default name
                        original_filename = model_data.get('original_filename', model_id)
                        model_data['name'] = os.path.splitext(original_filename)[0]
                        needs_save = True
                
                # Save if we made any changes
                if needs_save:
                    with open(self.metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
                
                return metadata
            except Exception as e:
                print(f"Warning: Could not load model metadata: {e}")
        return {}
    
    def _save_metadata(self):
        """Save model metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving model metadata: {e}")
    
    def _generate_model_id(self, filename: str, file_content: bytes) -> str:
        """Generate a unique model ID based on filename and content hash"""
        content_hash = hashlib.md5(file_content).hexdigest()[:8]
        base_name = os.path.splitext(filename)[0]
        return f"{base_name}_{content_hash}"
    
    def store_model(self, temp_file_path: str, original_filename: str, engine_type: str, description: str = "", name: str = "") -> str:
        """Store a model file in the repository and return model ID"""
        try:
            # Read file content for hashing
            with open(temp_file_path, 'rb') as f:
                file_content = f.read()
            
            # Generate unique model ID
            model_id = self._generate_model_id(original_filename, file_content)
            
            # Get file extension
            file_extension = os.path.splitext(original_filename)[1]
            stored_filename = f"{model_id}{file_extension}"
            stored_path = os.path.join(self.models_dir, stored_filename)
            
            # Copy file to repository
            shutil.copy2(temp_file_path, stored_path)
            
            # Get file size
            file_size = os.path.getsize(stored_path)
            
            # Use provided name or fall back to original filename without extension
            display_name = name.strip() if name.strip() else os.path.splitext(original_filename)[0]
            
            # Store metadata
            self.metadata[model_id] = {
                'id': model_id,
                'name': display_name,
                'original_filename': original_filename,
                'stored_filename': stored_filename,
                'stored_path': stored_path,
                'engine_type': engine_type,
                'description': description,
                'file_size': file_size,
                'upload_date': datetime.now().isoformat(),
                'file_extension': file_extension
            }
            
            self._save_metadata()
            return model_id
            
        except Exception as e:
            raise Exception(f"Failed to store model: {str(e)}")
    
    def get_model_path(self, model_id: str) -> Optional[str]:
        """Get the file path for a stored model"""
        if model_id in self.metadata:
            return self.metadata[model_id]['stored_path']
        return None
    
    def get_model_metadata(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific model"""
        return self.metadata.get(model_id)
    
    def list_models(self) -> Dict[str, Any]:
        """List all stored models with their metadata"""
        return dict(self.metadata)
    
    def delete_model(self, model_id: str) -> bool:
        """Delete a model from the repository"""
        if model_id not in self.metadata:
            return False
        
        try:
            # Delete file
            model_path = self.metadata[model_id]['stored_path']
            if os.path.exists(model_path):
                os.remove(model_path)
            
            # Remove from metadata
            del self.metadata[model_id]
            self._save_metadata()
            
            return True
        except Exception as e:
            print(f"Error deleting model {model_id}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        total_models = len(self.metadata)
        total_size = sum(model['file_size'] for model in self.metadata.values())
        
        # Group by engine type
        engine_counts = {}
        for model in self.metadata.values():
            engine_type = model['engine_type']
            engine_counts[engine_type] = engine_counts.get(engine_type, 0) + 1
        
        return {
            'total_models': total_models,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'engine_counts': engine_counts,
            'repository_path': self.repo_path
        }
