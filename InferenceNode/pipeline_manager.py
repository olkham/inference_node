
from __future__ import annotations
import sys
import os
import threading
import uuid
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ResultPublisher import ResultPublisher
from .pipeline import InferencePipeline

class PipelineManager:
    """Manages inference pipelines and their execution"""

    def __init__(self, repo_path: str, node_id: Optional[str] = None, node_name: Optional[str] = None):
        self.repo_path = repo_path
        
        # Create pipelines directory in InferenceNode folder for pipeline data
        inference_node_dir = os.path.dirname(os.path.abspath(__file__))
        self.pipelines_base_dir = os.path.join(inference_node_dir, 'pipelines')
        
        # Subdirectories for different pipeline data
        self.thumbnails_dir = os.path.join(self.pipelines_base_dir, 'thumbnails')
        self.metadata_file = os.path.join(self.pipelines_base_dir, 'pipelines_metadata.json')
        
        # Keep legacy pipelines_dir for backward compatibility (if needed)
        self.pipelines_dir = self.pipelines_base_dir
        
        self.active_pipelines = {}  # Dict[str, Dict] - pipeline_info
        self.pipeline_threads = {}  # Dict[str, threading.Thread]
        
        # Store node info for context variables in destinations
        self.node_id = node_id
        self.node_name = node_name
        
        # Set up logger
        self.logger = logging.getLogger(__name__)
        
        # Create directories if they don't exist
        os.makedirs(self.pipelines_base_dir, exist_ok=True)
        os.makedirs(self.thumbnails_dir, exist_ok=True)
        
        # Load existing metadata
        self.metadata = self._load_metadata()
        # Reset all pipeline statuses to 'stopped' on startup
        # (pipelines don't support auto-run on system start yet)
        for pipeline_id, pipeline_data in self.metadata.items():
            if pipeline_data.get('status') != 'stopped':
                pipeline_data['status'] = 'stopped'
        
        # Clear any stale active pipeline entries on startup
        self.active_pipelines.clear()
        self.pipeline_threads.clear()
                
        # Save the updated metadata
        self._save_metadata()
        
    
    def _cleanup_stale_pipeline_state(self, pipeline_id: str):
        """Clean up stale pipeline state entries"""
        if pipeline_id in self.active_pipelines:
            del self.active_pipelines[pipeline_id]
        if pipeline_id in self.pipeline_threads:
            del self.pipeline_threads[pipeline_id]
        # Also update metadata status
        if pipeline_id in self.metadata:
            self.metadata[pipeline_id]['status'] = 'stopped'
            self._save_metadata()

    def get_pipeline_status(self, pipeline_id: str) -> Optional[dict]:
        """Get the full status of the pipeline for API reporting."""
        pipeline = self.metadata.get(pipeline_id)
        if not pipeline:
            return None

        # Get runtime instance if running
        runtime = self.active_pipelines.get(pipeline_id, {})
        pipeline_instance = runtime.get('pipeline_instance') if runtime else None

        # Get publisher states
        publisher_states = self.get_pipeline_publisher_states(pipeline_id)

        # Get metrics
        stats = pipeline.get('stats', {})
        if pipeline_instance and hasattr(pipeline_instance, 'get_metrics'):
            try:
                stats = pipeline_instance.get_metrics()
            except Exception:
                pass

        # Preview state (if tracked)
        preview_enabled = False
        # If you have a preview tracking system, set preview_enabled accordingly

        return {
            'id': pipeline_id,
            'name': pipeline.get('name'),
            'status': pipeline.get('status'),
            'inference_enabled': pipeline.get('inference_enabled', True),
            'preview_enabled': preview_enabled,
            'stats': stats,
            'publishers': publisher_states,
            'destinations': pipeline.get('destinations', []),
            'created_date': pipeline.get('created_date'),
            'modified_date': pipeline.get('modified_date'),
            'model': pipeline.get('model'),
            'frame_source': pipeline.get('frame_source'),
        }
        
    def _load_metadata(self) -> Dict[str, Any]:
        """Load pipeline metadata from file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load pipeline metadata: {e}")
        return {}
    
    def _save_metadata(self):
        """Save pipeline metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving pipeline metadata: {e}")
    
    def _ensure_destination_uuid(self, dest_id: str) -> str:
        """Convert frontend destination ID to a proper UUID format"""
        if not dest_id:
            return str(uuid.uuid4())
        
        # If it's already a valid UUID format, return as-is
        try:
            uuid.UUID(dest_id)
            return dest_id
        except ValueError:
            # Convert frontend ID to a consistent UUID
            # Use a hash of the original ID to ensure consistency
            import hashlib
            hash_object = hashlib.md5(dest_id.encode())
            hex_dig = hash_object.hexdigest()
            # Convert to UUID format
            return f"{hex_dig[:8]}-{hex_dig[8:12]}-{hex_dig[12:16]}-{hex_dig[16:20]}-{hex_dig[20:32]}"

    def create_pipeline(self, config: Dict[str, Any]) -> str:
        """Create a new pipeline configuration"""
        pipeline_id = str(uuid.uuid4())
        
        # Process destinations to ensure they have enabled state and unique IDs
        processed_destinations = []
        for dest in config['destinations']:
            processed_dest = dest.copy()
            # Ensure each destination has an enabled state (default to True)
            if 'enabled' not in processed_dest:
                processed_dest['enabled'] = True
            # Ensure each destination has a proper UUID
            if 'id' not in processed_dest or not processed_dest['id']:
                processed_dest['id'] = str(uuid.uuid4())
            else:
                # Convert frontend ID to proper UUID format
                processed_dest['id'] = self._ensure_destination_uuid(processed_dest['id'])
            processed_destinations.append(processed_dest)
        
        pipeline_data = {
            'id': pipeline_id,
            'name': config['name'],
            'description': config.get('description', ''),
            'frame_source': config['frame_source'],
            'model': config['model'],
            'destinations': processed_destinations,
            'created_date': datetime.now().isoformat(),
            'status': 'stopped',
            'inference_enabled': config.get('inference_enabled', True),  # Default to enabled
            'stats': {
                'frame_count': 0,
                'inference_count': 0,
                'fps': 0,
                'latency_ms': 0
            }
        }
        
        # Save to metadata
        self.metadata[pipeline_id] = pipeline_data
        self._save_metadata()
        
        return pipeline_id
    
    def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get pipeline configuration"""
        return self.metadata.get(pipeline_id)
    
    def list_pipelines(self) -> Dict[str, Any]:
        """List all pipelines with current metrics"""
        pipelines_with_metrics = {}
        
        for pipeline_id, pipeline_data in self.metadata.items():
            # Create a copy of the pipeline data
            pipeline_copy = pipeline_data.copy()
            
            # If pipeline is running, get real-time metrics and publisher states
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                
                # Get real-time metrics
                if hasattr(pipeline_instance, 'get_metrics'):
                    try:
                        current_metrics = pipeline_instance.get_metrics()
                        # Update the stats with real-time data
                        pipeline_copy['stats'] = {
                            'frame_count': current_metrics.get('frame_count', 0),
                            'inference_count': current_metrics.get('inference_count', 0),
                            'fps': round(current_metrics.get('fps', 0), 1),
                            'latency_ms': round(current_metrics.get('latency_ms', 0), 1),
                            'elapsed_time': round(current_metrics.get('elapsed_time', 0), 1)
                        }
                        # Add uptime to the pipeline data
                        pipeline_copy['uptime'] = current_metrics.get('uptime', '0s')
                    except Exception as e:
                        print(f"Error getting metrics for pipeline {pipeline_id}: {e}")
                
                # Get enhanced publisher states with failure information
                if hasattr(pipeline_instance, 'get_publisher_states'):
                    try:
                        publisher_states = pipeline_instance.get_publisher_states()
                        # Update destinations with enhanced state information
                        if 'destinations' in pipeline_copy and publisher_states:
                            for dest in pipeline_copy['destinations']:
                                dest_id = dest.get('id')
                                if dest_id in publisher_states:
                                    state = publisher_states[dest_id]
                                    dest['failure_count'] = state.get('failure_count', 0)
                                    dest['auto_disabled'] = state.get('auto_disabled', False)
                                    dest['last_error'] = state.get('last_error', None)
                    except Exception as e:
                        print(f"Error getting publisher states for pipeline {pipeline_id}: {e}")
            
            pipelines_with_metrics[pipeline_id] = pipeline_copy
            
        return pipelines_with_metrics
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get a summary of pipelines for discovery service"""
        all_pipelines = self.list_pipelines()
        
        total_pipelines = len(all_pipelines)
        active_pipelines = len([p for p in all_pipelines.values() if p.get('status') == 'running'])
        
        # Calculate averages
        total_fps = sum(p.get('stats', {}).get('fps', 0) for p in all_pipelines.values())
        avg_fps = round(total_fps / max(active_pipelines, 1), 1) if active_pipelines > 0 else 0
        
        total_latency = sum(p.get('stats', {}).get('latency_ms', 0) for p in all_pipelines.values())
        avg_latency = round(total_latency / max(active_pipelines, 1), 1) if active_pipelines > 0 else 0
        
        # Get pipeline details for cards
        pipeline_cards = []
        for pipeline_id, pipeline_data in all_pipelines.items():
            card_data = {
                'id': pipeline_id,
                'name': pipeline_data.get('name', 'Unnamed Pipeline'),
                'description': pipeline_data.get('description', ''),
                'status': pipeline_data.get('status', 'stopped'),
                'model': pipeline_data.get('model', {}),
                'frame_source': pipeline_data.get('frame_source', {}),
                'stats': pipeline_data.get('stats', {}),
                'created_date': pipeline_data.get('created_date'),
                'inference_enabled': pipeline_data.get('inference_enabled', True)
            }
            pipeline_cards.append(card_data)
        
        return {
            'total_pipelines': total_pipelines,
            'active_pipelines': active_pipelines,
            'avg_fps': avg_fps,
            'avg_latency': avg_latency,
            'pipeline_cards': pipeline_cards
        }
    
    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a pipeline"""
        if pipeline_id not in self.metadata:
            return False
        
        # Stop pipeline if running
        self.stop_pipeline(pipeline_id)
        
        # Delete thumbnail if it exists
        self.delete_pipeline_thumbnail(pipeline_id)
        
        # Remove from metadata
        del self.metadata[pipeline_id]
        self._save_metadata()
        
        return True
    
    def update_pipeline(self, pipeline_id: str, config: Dict[str, Any]) -> bool:
        """Update an existing pipeline configuration"""
        if pipeline_id not in self.metadata:
            return False
        
        # Don't allow updating running pipelines
        if pipeline_id in self.active_pipelines:
            return False
        
        # Update the pipeline data, preserving existing fields not in config
        pipeline_data = self.metadata[pipeline_id]
        
        # Update basic info
        if 'name' in config:
            pipeline_data['name'] = config['name']
        if 'description' in config:
            pipeline_data['description'] = config['description']
        if 'frame_source' in config:
            pipeline_data['frame_source'] = config['frame_source']
        if 'model' in config:
            pipeline_data['model'] = config['model']
        if 'destinations' in config:
            # Process destinations to preserve IDs and enabled states from existing destinations
            processed_destinations = []
            existing_destinations = pipeline_data.get('destinations', [])
            
            for new_dest in config['destinations']:
                processed_dest = new_dest.copy()
                
                # First try to find existing destination by ID if provided
                existing_dest = None
                if 'id' in new_dest and new_dest['id']:
                    for existing in existing_destinations:
                        if existing.get('id') == new_dest['id']:
                            existing_dest = existing
                            break
                
                # If not found by ID, try to match by type and config
                if not existing_dest:
                    for existing in existing_destinations:
                        if (existing.get('type') == new_dest.get('type') and 
                            existing.get('config') == new_dest.get('config')):
                            existing_dest = existing
                            break
                
                if existing_dest:
                    # Preserve existing ID, but allow enabled state to be updated from frontend
                    processed_dest['id'] = existing_dest.get('id', str(uuid.uuid4()))
                    # Use the enabled state from the frontend (allow UI changes to persist)
                    processed_dest['enabled'] = processed_dest.get('enabled', existing_dest.get('enabled', True))
                else:
                    # New destination - assign new ID if not provided and default to enabled
                    if 'id' not in processed_dest or not processed_dest['id']:
                        processed_dest['id'] = str(uuid.uuid4())
                    else:
                        # Convert frontend ID to proper UUID format
                        processed_dest['id'] = self._ensure_destination_uuid(processed_dest['id'])
                    processed_dest['enabled'] = processed_dest.get('enabled', True)
                
                processed_destinations.append(processed_dest)
            
            pipeline_data['destinations'] = processed_destinations
        if 'inference_enabled' in config:
            pipeline_data['inference_enabled'] = config['inference_enabled']
        
        # Update modified date
        pipeline_data['modified_date'] = datetime.now().isoformat()
        
        # Save to metadata
        self.metadata[pipeline_id] = pipeline_data
        self._save_metadata()
        
        return True
    
    def start_pipeline(self, pipeline_id: str, model_repo, result_publisher) -> bool:
        """Start a pipeline in a background thread"""
        if pipeline_id not in self.metadata:
            self.logger.error(f"Cannot start pipeline {pipeline_id} - not found in metadata")
            return False
        
        # Check if pipeline is actually running, not just in the dictionary
        if pipeline_id in self.active_pipelines:
            active_pipeline = self.active_pipelines[pipeline_id]
            # Check if the pipeline instance exists and is actually running
            if 'pipeline_instance' in active_pipeline:
                pipeline_instance = active_pipeline['pipeline_instance']
                
                # Use the pipeline's state tracking to determine if it's actually running
                if hasattr(pipeline_instance, 'is_running') and pipeline_instance.is_running():
                    self.logger.warning(f"Cannot start pipeline {pipeline_id} - already running")
                    return False
                else:
                    self.logger.info(f"Cleaning up stale pipeline {pipeline_id} entry")
                    # Clean up stale entry
                    self._cleanup_stale_pipeline_state(pipeline_id)
            else:
                self.logger.info(f"Cleaning up incomplete pipeline {pipeline_id} entry")
                # Clean up incomplete entry
                self._cleanup_stale_pipeline_state(pipeline_id)
        
        pipeline_config = self.metadata[pipeline_id]
        self.logger.info(f"Starting pipeline {pipeline_id} ({pipeline_config.get('name', 'Unknown')})")
        self.logger.debug(f"Pipeline status: {pipeline_config.get('status', 'unknown')}, Active pipelines count: {len(self.active_pipelines)}")
        
        # Check if this is a folder source and log the folder path
        frame_source = pipeline_config.get('frame_source', {})
        if frame_source.get('capture_type') in ['image_folder', 'folder']:
            folder_path = frame_source.get('config', {}).get('source', 'Unknown')
            self.logger.info(f"Folder source detected - watching folder: {folder_path}")
        
        try:
            # Create a startup status indicator
            startup_status = {'started': False, 'error': None}
            
            # Create pipeline thread with startup status callback
            pipeline_thread = threading.Thread(
                target=self._run_pipeline,
                args=(pipeline_id, pipeline_config, model_repo, result_publisher, startup_status),
                daemon=True
            )
            
            # Mark as starting
            self.metadata[pipeline_id]['status'] = 'starting'
            self.active_pipelines[pipeline_id] = {
                'config': pipeline_config,
                'start_time': time.time(),
                'frame_count': 0,
                'inference_count': 0,
                'startup_status': startup_status
            }
            
            self.logger.debug(f"Starting thread for pipeline {pipeline_id}")
            # Start thread
            pipeline_thread.start()
            self.pipeline_threads[pipeline_id] = pipeline_thread
            
            # Wait for pipeline to actually start or fail (max 10 seconds)
            max_wait_time = 10  # seconds
            wait_interval = 0.1  # seconds
            total_waited = 0
            
            while total_waited < max_wait_time:
                if startup_status['started']:
                    # Pipeline started successfully
                    self.metadata[pipeline_id]['status'] = 'running'
                    self._save_metadata()
                    print(f"PipelineManager: Pipeline {pipeline_id} started successfully")
                    return True
                elif startup_status['error']:
                    # Pipeline failed to start
                    print(f"PipelineManager: Pipeline {pipeline_id} failed to start: {startup_status['error']}")
                    # Clean up
                    if pipeline_id in self.active_pipelines:
                        del self.active_pipelines[pipeline_id]
                    self.metadata[pipeline_id]['status'] = 'error'
                    self._save_metadata()
                    return False
                
                time.sleep(wait_interval)
                total_waited += wait_interval
            
            # Timeout - pipeline didn't start in time
            print(f"PipelineManager: Timeout waiting for pipeline {pipeline_id} to start")
            if pipeline_id in self.active_pipelines:
                del self.active_pipelines[pipeline_id]
            self.metadata[pipeline_id]['status'] = 'error'
            self._save_metadata()
            return False
            
        except Exception as e:
            print(f"PipelineManager: Error starting pipeline {pipeline_id}: {e}")
            return False
    
    def stop_pipeline(self, pipeline_id: str) -> bool:
        """Stop a running pipeline"""
        # if pipeline_id not in self.active_pipelines:
            # return False
        
        try:
            # Stop the pipeline instance if it exists
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                if hasattr(pipeline_instance, 'stop'):
                    pipeline_instance.stop()
            
            # Mark as stopped
            if pipeline_id in self.metadata:
                self.metadata[pipeline_id]['status'] = 'stopped'
            
            # Remove from active pipelines
            if pipeline_id in self.active_pipelines:
                del self.active_pipelines[pipeline_id]
            
            # Note: Thread will stop on next iteration when it checks active_pipelines
            if pipeline_id in self.pipeline_threads:
                del self.pipeline_threads[pipeline_id]
            
            self._save_metadata()
            return True
            
        except Exception as e:
            print(f"Error stopping pipeline {pipeline_id}: {e}")
            return False
    
    def enable_pipeline_inference(self, pipeline_id: str) -> bool:
        """Enable inference for a pipeline"""
        try:
            # Update metadata
            if pipeline_id in self.metadata:
                self.metadata[pipeline_id]['inference_enabled'] = True
                self._save_metadata()
            
            # Update running pipeline instance
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                if hasattr(pipeline_instance, 'enable_inference'):
                    pipeline_instance.enable_inference()
            
            return True
        except Exception as e:
            print(f"Error enabling inference for pipeline {pipeline_id}: {e}")
            return False
    
    def disable_pipeline_inference(self, pipeline_id: str) -> bool:
        """Disable inference for a pipeline"""
        try:
            # Update metadata
            if pipeline_id in self.metadata:
                self.metadata[pipeline_id]['inference_enabled'] = False
                self._save_metadata()
            
            # Update running pipeline instance
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                if hasattr(pipeline_instance, 'disable_inference'):
                    pipeline_instance.disable_inference()
            
            return True
        except Exception as e:
            print(f"Error disabling inference for pipeline {pipeline_id}: {e}")
            return False
    
    def set_pipeline_confidence_threshold(self, pipeline_id: str, threshold: float) -> bool:
        """Set the confidence threshold for a pipeline's inference engine
        
        Args:
            pipeline_id: The pipeline ID
            threshold: Confidence threshold value (0.0 to 1.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate threshold
            if not 0.0 <= threshold <= 1.0:
                self.logger.error(f"Invalid confidence threshold {threshold}, must be between 0.0 and 1.0")
                return False
            
            # If pipeline is running, set threshold on the running instance
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                success = pipeline_instance.set_confidence_threshold(threshold)
                if success:
                    self.logger.info(f"Set confidence threshold to {threshold} for running pipeline {pipeline_id}")
                    
                    # Also update metadata for persistence
                    if pipeline_id in self.metadata:
                        if 'model' not in self.metadata[pipeline_id]:
                            self.metadata[pipeline_id]['model'] = {}
                        self.metadata[pipeline_id]['model']['conf_threshold'] = threshold
                        self._save_metadata()
                    
                    return True
                else:
                    self.logger.error(f"Failed to set confidence threshold for running pipeline {pipeline_id}")
                    return False
            else:
                # Pipeline not running, just update metadata for next run
                if pipeline_id in self.metadata:
                    if 'model' not in self.metadata[pipeline_id]:
                        self.metadata[pipeline_id]['model'] = {}
                    self.metadata[pipeline_id]['model']['conf_threshold'] = threshold
                    self._save_metadata()
                    self.logger.info(f"Updated confidence threshold to {threshold} in metadata for pipeline {pipeline_id}")
                    return True
                else:
                    self.logger.error(f"Pipeline {pipeline_id} not found")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error setting confidence threshold for pipeline {pipeline_id}: {e}")
            return False
    
    def get_pipeline_confidence_threshold(self, pipeline_id: str) -> Optional[float]:
        """Get the confidence threshold for a pipeline
        
        Args:
            pipeline_id: The pipeline ID
            
        Returns:
            float: Current confidence threshold, or None if not available
        """
        try:
            # If pipeline is running, get from running instance
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                threshold = pipeline_instance.get_confidence_threshold()
                if threshold is not None:
                    return threshold
            
            # Otherwise get from metadata
            if pipeline_id in self.metadata:
                model_config = self.metadata[pipeline_id].get('model', {})
                return model_config.get('conf_threshold', 0.25)  # Default to 0.25
            
            return None
        except Exception as e:
            self.logger.error(f"Error getting confidence threshold for pipeline {pipeline_id}: {e}")
            return None

    def enable_pipeline_publisher(self, pipeline_id: str, publisher_id: str) -> bool:
        """Enable a specific publisher for a pipeline"""
        try:
            print(f"DEBUG: enable_pipeline_publisher called with pipeline_id='{pipeline_id}', publisher_id='{publisher_id}'")
            
            # Update metadata
            if pipeline_id in self.metadata:
                destinations = self.metadata[pipeline_id].get('destinations', [])
                for dest in destinations:
                    if str(dest.get('id')) == str(publisher_id):
                        dest['enabled'] = True
                        print(f"DEBUG: Updated metadata for destination {publisher_id} to enabled=True")
                        break
                else:
                    print(f"DEBUG: Publisher {publisher_id} not found in metadata destinations")
                    # Print all destination IDs for debugging
                    print(f"DEBUG: Available destination IDs: {[str(dest.get('id')) for dest in destinations]}")
                self._save_metadata()
            else:
                print(f"DEBUG: Pipeline {pipeline_id} not found in metadata")
            
            # Update running pipeline instance
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                if hasattr(pipeline_instance, 'enable_publisher'):
                    print(f"DEBUG: Calling enable_publisher on pipeline instance")
                    pipeline_instance.enable_publisher(publisher_id)
                else:
                    print(f"DEBUG: Pipeline instance does not have enable_publisher method")
            else:
                print(f"DEBUG: Pipeline {pipeline_id} not found in active_pipelines or no pipeline_instance")
            
            return True
        except Exception as e:
            print(f"Error enabling publisher {publisher_id} for pipeline {pipeline_id}: {e}")
            return False

    def disable_pipeline_publisher(self, pipeline_id: str, publisher_id: str) -> bool:
        """Disable a specific publisher for a pipeline"""
        try:
            print(f"DEBUG: disable_pipeline_publisher called with pipeline_id='{pipeline_id}', publisher_id='{publisher_id}'")
            
            # Update metadata
            if pipeline_id in self.metadata:
                destinations = self.metadata[pipeline_id].get('destinations', [])
                for dest in destinations:
                    if str(dest.get('id')) == str(publisher_id):
                        dest['enabled'] = False
                        print(f"DEBUG: Updated metadata for destination {publisher_id} to enabled=False")
                        break
                else:
                    print(f"DEBUG: Publisher {publisher_id} not found in metadata destinations")
                    # Print all destination IDs for debugging
                    print(f"DEBUG: Available destination IDs: {[str(dest.get('id')) for dest in destinations]}")
                self._save_metadata()
            else:
                print(f"DEBUG: Pipeline {pipeline_id} not found in metadata")
            
            # Update running pipeline instance
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                if hasattr(pipeline_instance, 'disable_publisher'):
                    print(f"DEBUG: Calling disable_publisher on pipeline instance")
                    pipeline_instance.disable_publisher(publisher_id)
                else:
                    print(f"DEBUG: Pipeline instance does not have disable_publisher method")
            else:
                print(f"DEBUG: Pipeline {pipeline_id} not found in active_pipelines or no pipeline_instance")
            
            return True
        except Exception as e:
            print(f"Error disabling publisher {publisher_id} for pipeline {pipeline_id}: {e}")
            return False

    def get_pipeline_publisher_states(self, pipeline_id: str) -> Dict[str, Any]:
        """Get the current state of all publishers for a pipeline"""
        try:
            if pipeline_id not in self.metadata:
                return {}
            
            # Get states from metadata
            metadata_states = {}
            destinations = self.metadata[pipeline_id].get('destinations', [])
            for dest in destinations:
                dest_id = dest.get('id')
                if dest_id:
                    metadata_states[dest_id] = {
                        'enabled': dest.get('enabled', True),
                        'type': dest.get('type', 'unknown'),
                        'configured': True
                    }
            
            # Get real-time states from running pipeline if available
            if pipeline_id in self.active_pipelines and 'pipeline_instance' in self.active_pipelines[pipeline_id]:
                pipeline_instance = self.active_pipelines[pipeline_id]['pipeline_instance']
                if hasattr(pipeline_instance, 'get_publisher_states'):
                    try:
                        runtime_states = pipeline_instance.get_publisher_states()
                        # Merge runtime states with metadata states
                        for publisher_id, runtime_state in runtime_states.items():
                            # Ensure publisher_id is a string for JSON serialization
                            str_publisher_id = str(publisher_id)
                            if str_publisher_id in metadata_states:
                                metadata_states[str_publisher_id].update(runtime_state)
                    except Exception:
                        pass  # Silently continue if runtime states fail
            
            # Ensure all keys in the final dictionary are strings for JSON serialization
            string_keyed_states = {}
            for key, value in metadata_states.items():
                string_keyed_states[str(key)] = value
            
            return string_keyed_states
        except Exception as e:
            print(f"Error in get_pipeline_publisher_states for pipeline {pipeline_id}: {e}")
            print(f"Exception type: {type(e)}")
            import traceback
            traceback.print_exc()
            return {}
    
    def get_pipeline_thumbnail_path(self, pipeline_id: str) -> Optional[str]:
        """Get the thumbnail path for a pipeline"""
        thumbnail_path = os.path.join(self.thumbnails_dir, f"thumbnail_{pipeline_id}.jpg")
        file_exists = os.path.exists(thumbnail_path)
        print(f"PipelineManager: get_pipeline_thumbnail_path({pipeline_id}) -> {thumbnail_path}, exists: {file_exists}")
        if file_exists:
            return thumbnail_path
        return None
    
    def has_pipeline_thumbnail(self, pipeline_id: str) -> bool:
        """Check if a pipeline has a thumbnail"""
        result = self.get_pipeline_thumbnail_path(pipeline_id) is not None
        print(f"PipelineManager: has_pipeline_thumbnail({pipeline_id}) -> {result}")
        return result
    
    def delete_pipeline_thumbnail(self, pipeline_id: str):
        """Delete a pipeline's thumbnail file"""
        thumbnail_path = os.path.join(self.thumbnails_dir, f"thumbnail_{pipeline_id}.jpg")
        if os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
                print(f"Deleted thumbnail for pipeline {pipeline_id}")
            except Exception as e:
                print(f"Failed to delete thumbnail for pipeline {pipeline_id}: {e}")

    def generate_pipeline_thumbnail(self, pipeline_id: str) -> bool:
        """Generate a fresh thumbnail for a pipeline from its current frame"""
        try:
            # Check if pipeline exists and is running
            if pipeline_id not in self.active_pipelines:
                print(f"Pipeline {pipeline_id} is not active, cannot generate thumbnail")
                return False
            
            # Get the pipeline instance
            active_pipeline = self.active_pipelines[pipeline_id]
            if 'pipeline_instance' not in active_pipeline:
                print(f"Pipeline {pipeline_id} has no instance, cannot generate thumbnail")
                return False
            
            pipeline_instance = active_pipeline['pipeline_instance']
            
            # Get the latest frame from the pipeline
            if not hasattr(pipeline_instance, 'get_latest_frame'):
                print(f"Pipeline {pipeline_id} does not support frame access")
                return False
            
            current_frame = pipeline_instance.get_latest_frame()
            if current_frame is None:
                print(f"Pipeline {pipeline_id} has no current frame available")
                return False
            
            # Set thumbnail path if not already set
            if not hasattr(pipeline_instance, 'set_thumbnail_path') or not hasattr(pipeline_instance, 'capture_thumbnail'):
                print(f"Pipeline {pipeline_id} does not support thumbnail capture")
                return False
            
            # Ensure thumbnails directory exists
            os.makedirs(self.thumbnails_dir, exist_ok=True)
            
            # Set the thumbnail path on the pipeline instance
            pipeline_instance.set_thumbnail_path(self.thumbnails_dir)
            
            # Capture the thumbnail from the current frame
            success = pipeline_instance.capture_thumbnail(current_frame)
            
            if success:
                print(f"Successfully generated thumbnail for pipeline {pipeline_id}")
                return True
            else:
                print(f"Failed to capture thumbnail for pipeline {pipeline_id}")
                return False
                
        except Exception as e:
            print(f"Error generating thumbnail for pipeline {pipeline_id}: {e}")
            return False

    def _initialize_pipeline(self, pipeline_id: str, config: Dict[str, Any], model_repo) -> InferencePipeline:
        """Initialize and configure a pipeline instance
        
        Args:
            pipeline_id: The unique identifier for the pipeline
            config: The pipeline configuration dictionary
            model_repo: The model repository to get model paths from
            
        Returns:
            Configured InferencePipeline instance
            
        Raises:
            Exception: If pipeline initialization fails
        """
        # Create pipeline instance
        pipeline = InferencePipeline()
        pipeline.id = pipeline_id
        
        # Configure frame source
        frame_source_config = config['frame_source']
        # Extract the proper configuration for FrameSourceFactory
        frame_source_type = frame_source_config.get('capture_type', 'webcam')  # UI sends 'type', not 'capture_type'
        frame_source_settings = frame_source_config.get('config', {})
        
        # Map UI capture types to FrameSourceFactory types
        capture_type_mapping = {
            'ip_camera': 'ipcam',  # UI uses 'ip_camera', FrameSourceFactory expects 'ipcam'
            'image_folder': 'folder',  # UI uses 'image_folder', FrameSourceFactory expects 'folder'
            # Add other mappings as needed
        }
        
        # Apply mapping if needed
        mapped_capture_type = capture_type_mapping.get(frame_source_type, frame_source_type)
        
        # Create the frame source configuration that FrameSourceFactory expects
        final_frame_config = {
            'capture_type': mapped_capture_type,
            **frame_source_settings
        }
        
        # For folder sources, ensure watch mode is enabled to keep pipeline active
        if mapped_capture_type == 'folder':
            # Enable watch mode for folder sources to keep pipeline running even when folder is empty
            final_frame_config['watch'] = True
            print(f"Pipeline {pipeline_id}: Folder source configured with watch mode enabled")
            if not frame_source_settings.get('source'):
                print(f"Pipeline {pipeline_id}: Warning - no source folder specified for folder capture")
            else:
                source_folder = frame_source_settings.get('source')
                print(f"Pipeline {pipeline_id}: Watching folder: {source_folder}")
                # Create the folder if it doesn't exist
                if not os.path.exists(source_folder):
                    try:
                        os.makedirs(source_folder, exist_ok=True)
                        print(f"Pipeline {pipeline_id}: Created folder: {source_folder}")
                    except Exception as e:
                        print(f"Pipeline {pipeline_id}: Warning - could not create folder {source_folder}: {e}")
        
        print(f"Pipeline {pipeline_id}: Final frame source config: {final_frame_config}")
        
        # Configure inference engine
        model_config = config['model']
        engine = model_config.get('engine_type', 'ultralytics')
        
        # Handle Pass engine specially - it doesn't need a model
        if engine == 'pass':
            model_path = None
        else:
            model_path = model_repo.get_model_path(model_config['id'])
            if not model_path:
                raise Exception(f"Model {model_config['id']} not found")

        # Prepare inference engine configuration
        device = model_config.get('device', 'cpu')  # Default to cpu if not specified

        # Validate device availability based on engine type
        if engine in ['geti']:
            # For OpenVINO-based engines (GETI), validate OpenVINO devices
            if device.lower() in ['gpu', 'intel:gpu']:
                # Convert to OpenVINO format and validate
                device = 'GPU'  # OpenVINO expects uppercase
                try:
                    from openvino.runtime import Core
                    core = Core()
                    available_devices = core.available_devices
                    if not any('GPU' in dev for dev in available_devices):
                        print(f"WARNING: Intel GPU requested but not available in OpenVINO. Available devices: {available_devices}. Falling back to CPU.")
                        device = 'CPU'
                except ImportError:
                    print(f"WARNING: OpenVINO not available to validate GPU device. Falling back to CPU.")
                    device = 'CPU'
                except Exception as e:
                    print(f"WARNING: Error checking OpenVINO devices: {e}. Falling back to CPU.")
                    device = 'CPU'
            elif device.lower() in ['cpu', 'intel:cpu']:
                device = 'CPU'  # OpenVINO expects uppercase
        else:
            # For PyTorch-based engines (ultralytics, torch), validate CUDA devices
            if device in ['cuda', '0', 'gpu', 'nvidia:gpu'] or (isinstance(device, str) and device.isdigit()):
                try:
                    import torch
                    if not torch.cuda.is_available():
                        print(f"WARNING: CUDA device '{device}' requested but CUDA is not available. Falling back to CPU.")
                        device = 'cpu'
                except ImportError:
                    print(f"WARNING: PyTorch not available to check CUDA. Falling back to CPU for device '{device}'.")
                    device = 'cpu'

        if engine == 'pass':
            # Pass engine doesn't need model_path
            inference_config = {'engine_type': engine, 'device': device}
        else:
            inference_config = {'engine_type': engine, 'model_path': model_path, 'device': device, 'task': 'detect'}

        # Configure result publisher with destinations
        pipeline_publisher = ResultPublisher()
        for dest_config in config['destinations']:
            # Store the destination ID for later reference
            dest_id = dest_config.get('id')
            dest_enabled = dest_config.get('enabled', True)
            
            # Create destination based on type
            if dest_config['type'] == 'mqtt':
                from ResultPublisher.result_destinations import MQTTDestination
                dest = MQTTDestination()
                # Set context variables for variable substitution
                # Note: We need to get these from the InferenceNode instance
                # For now, we'll need to pass them to the pipeline manager
                if hasattr(self, 'node_id') and hasattr(self, 'node_name'):
                    dest.set_context_variables(
                        node_id=self.node_id,
                        node_name=self.node_name
                    )
                
                # Configure destination with error handling
                try:
                    dest.configure(**dest_config['config'])
                    # Set the destination ID and enabled state
                    if dest_id:
                        dest._id = dest_id
                    dest.enabled = dest_enabled
                    pipeline_publisher.add(dest)
                    print(f"Successfully configured MQTT destination: {dest_config['config'].get('server', 'unknown')}")
                except Exception as e:
                    print(f"Failed to configure MQTT destination: {str(e)} - Pipeline will continue without this destination")
            elif dest_config['type'] == 'webhook':
                from ResultPublisher.result_destinations import WebhookDestination
                dest = WebhookDestination()
                # Set context variables for variable substitution
                if hasattr(self, 'node_id') and hasattr(self, 'node_name'):
                    dest.set_context_variables(
                        node_id=self.node_id,
                        node_name=self.node_name
                    )
                
                # Configure destination with error handling
                try:
                    dest.configure(**dest_config['config'])
                    # Set the destination ID and enabled state
                    if dest_id:
                        dest._id = dest_id
                    dest.enabled = dest_enabled
                    pipeline_publisher.add(dest)
                    print(f"Successfully configured Webhook destination: {dest_config['config'].get('url', 'unknown')}")
                except Exception as e:
                    print(f"Failed to configure Webhook destination: {str(e)} - Pipeline will continue without this destination")
            elif dest_config['type'] == 'null':
                from ResultPublisher.result_destinations import NullDestination
                dest = NullDestination()
                # Set context variables for variable substitution
                if hasattr(self, 'node_id') and hasattr(self, 'node_name'):
                    dest.set_context_variables(
                        node_id=self.node_id,
                        node_name=self.node_name
                    )
                
                # Configure destination with error handling
                try:
                    dest.configure(**dest_config.get('config', {}))
                    # Set the destination ID and enabled state
                    if dest_id:
                        dest._id = dest_id
                    dest.enabled = dest_enabled
                    pipeline_publisher.add(dest)
                    print(f"Successfully configured Null destination")
                except Exception as e:
                    print(f"Failed to configure Null destination: {str(e)} - Pipeline will continue without this destination")
            elif dest_config['type'] == 'serial':
                from ResultPublisher.result_destinations import SerialDestination
                dest = SerialDestination()
                # Set context variables for variable substitution
                if hasattr(self, 'node_id') and hasattr(self, 'node_name'):
                    dest.set_context_variables(
                        node_id=self.node_id,
                        node_name=self.node_name
                    )
                
                # Configure destination with error handling
                try:
                    dest.configure(**dest_config['config'])
                    # Set the destination ID and enabled state
                    if dest_id:
                        dest._id = dest_id
                    dest.enabled = dest_enabled
                    pipeline_publisher.add(dest)
                    print(f"Successfully configured Serial destination: {dest_config['config'].get('com_port', 'unknown')}")
                except Exception as e:
                    print(f"Failed to configure Serial destination: {str(e)} - Pipeline will continue without this destination")
            elif dest_config['type'] == 'folder':
                from ResultPublisher.result_destinations import FolderDestination
                dest = FolderDestination()
                # Set context variables for variable substitution
                if hasattr(self, 'node_id') and hasattr(self, 'node_name'):
                    dest.set_context_variables(
                        node_id=self.node_id,
                        node_name=self.node_name
                    )
                
                # Configure destination with error handling
                try:
                    dest.configure(**dest_config['config'])
                    # Set the destination ID and enabled state
                    if dest_id:
                        dest._id = dest_id
                    dest.enabled = dest_enabled
                    pipeline_publisher.add(dest)
                    print(f"Successfully configured File destination: {dest_config['config'].get('folder_path', 'unknown')}")
                except Exception as e:
                    print(f"Failed to configure File destination: {str(e)} - Pipeline will continue without this destination")
            elif dest_config['type'] == 'roboflow':
                from ResultPublisher.result_destinations import RoboflowDestination
                dest = RoboflowDestination()
                # Set context variables for variable substitution
                if hasattr(self, 'node_id') and hasattr(self, 'node_name'):
                    dest.set_context_variables(
                        node_id=self.node_id,
                        node_name=self.node_name
                    )
                
                # Configure destination with error handling
                try:
                    dest.configure(**dest_config['config'])
                    # Set the destination ID and enabled state
                    if dest_id:
                        dest._id = dest_id
                    dest.enabled = dest_enabled
                    pipeline_publisher.add(dest)
                    print(f"Successfully configured Roboflow destination: {dest_config['config'].get('workspace_id', 'unknown')}/{dest_config['config'].get('project_id', 'unknown')}")
                except Exception as e:
                    print(f"Failed to configure Roboflow destination: {str(e)} - Pipeline will continue without this destination")
            elif dest_config['type'] == 'geti':
                from ResultPublisher.result_destinations import GetiDestination
                dest = GetiDestination()
                # Set context variables for variable substitution
                if hasattr(self, 'node_id') and hasattr(self, 'node_name'):
                    dest.set_context_variables(
                        node_id=self.node_id,
                        node_name=self.node_name
                    )
                
                # Configure destination with error handling
                try:
                    dest.configure(**dest_config['config'])
                    # Set the destination ID and enabled state
                    if dest_id:
                        dest._id = dest_id
                    dest.enabled = dest_enabled
                    pipeline_publisher.add(dest)
                    project_identifier = dest_config['config'].get('project_name') or dest_config['config'].get('project_id', 'unknown')
                    print(f"Successfully configured Geti destination: {dest_config['config'].get('host', 'unknown')} -> {project_identifier}")
                except Exception as e:
                    print(f"Failed to configure Geti destination: {str(e)} - Pipeline will continue without this destination")
            else:
                print(f"Unknown destination type: {dest_config['type']} - Skipping this destination")
            # Add more destination types as needed
        
        # Configure the pipeline
        pipeline.configure(
            frame_source_config=final_frame_config,
            inference_engine_config=inference_config,
            result_publisher=pipeline_publisher
        )
        
        # Set up thumbnail path for the pipeline
        pipeline.set_thumbnail_path(self.thumbnails_dir)
        
        # Set initial inference enabled state
        inference_enabled = config.get('inference_enabled', True)
        if inference_enabled:
            pipeline.enable_inference()
        else:
            pipeline.disable_inference()
        
        return pipeline

    def _run_pipeline(self, pipeline_id: str, config: Dict[str, Any], model_repo, result_publisher, startup_status=None):
        """Run a pipeline in a background thread
        
        Args:
            pipeline_id: The unique identifier for the pipeline
            config: The pipeline configuration dictionary
            model_repo: The model repository to get model paths from
            result_publisher: The result publisher (unused, kept for compatibility)
            startup_status: Optional dict to signal startup success/failure
        """
        try:
            # Initialize and configure the pipeline
            pipeline = self._initialize_pipeline(pipeline_id, config, model_repo)
            
            # Store the pipeline instance so we can stop it
            self.active_pipelines[pipeline_id]['pipeline_instance'] = pipeline
            
            print(f"Starting pipeline {pipeline_id}: {config['name']}")
            
            # Use the pipeline's own start method which handles threading internally
            pipeline.start()
            
            # Signal successful startup
            if startup_status:
                startup_status['started'] = True
            
            # Keep track of the pipeline until it's stopped
            while pipeline_id in self.active_pipelines:
                time.sleep(1)
                # Check if pipeline is still running using the pipeline's state
                if hasattr(pipeline, 'is_running') and not pipeline.is_running():
                    print(f"Pipeline {pipeline_id} is no longer running")
                    # Check if this was due to an error
                    if pipeline_id in self.active_pipelines:
                        if hasattr(pipeline, 'has_error') and pipeline.has_error():
                            print(f"Pipeline {pipeline_id} stopped with error: {pipeline.get_error()}")
                            if pipeline_id in self.metadata:
                                self.metadata[pipeline_id]['status'] = 'error'
                                # Also disable inference when pipeline errors
                                self.metadata[pipeline_id]['inference_enabled'] = False
                        else:
                            print(f"Pipeline {pipeline_id} stopped normally")
                        # Clean up both active pipelines and threads
                        self._cleanup_stale_pipeline_state(pipeline_id)
                    break
            
            print(f"Pipeline {pipeline_id} stopped")
            
        except Exception as e:
            print(f"Pipeline {pipeline_id} error: {e}")
            
            # Signal startup failure
            if startup_status:
                startup_status['error'] = str(e)
            
            # Mark as error and disable inference on error  
            self._cleanup_stale_pipeline_state(pipeline_id)
            if pipeline_id in self.metadata:
                self.metadata[pipeline_id]['status'] = 'error'
                self.metadata[pipeline_id]['inference_enabled'] = False
                self._save_metadata()
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get overall pipeline statistics with real-time metrics"""
        total_pipelines = len(self.metadata)
        active_pipelines = len(self.active_pipelines)
        
        # Calculate average FPS and latency across active pipelines using real-time data
        avg_fps = 0
        avg_latency = 0
        if active_pipelines > 0:
            total_fps = 0
            total_latency = 0
            valid_fps_count = 0
            valid_latency_count = 0
            
            for pipeline_id, pipeline_info in self.active_pipelines.items():
                if 'pipeline_instance' in pipeline_info:
                    pipeline_instance = pipeline_info['pipeline_instance']
                    if hasattr(pipeline_instance, 'get_metrics'):
                        try:
                            metrics = pipeline_instance.get_metrics()
                            fps = metrics.get('fps', 0)
                            if fps > 0:
                                total_fps += fps
                                valid_fps_count += 1
                            
                            # Get actual inference latency from pipeline metrics
                            latency = metrics.get('latency_ms', 0)
                            if latency > 0:
                                total_latency += latency
                                valid_latency_count += 1
                        except Exception as e:
                            print(f"Error getting metrics for pipeline {pipeline_id}: {e}")
            
            if valid_fps_count > 0:
                avg_fps = total_fps / valid_fps_count
            if valid_latency_count > 0:
                avg_latency = total_latency / valid_latency_count
        
        return {
            'total': total_pipelines,
            'active': active_pipelines,
            'avg_fps': round(avg_fps, 1),
            'avg_latency': round(avg_latency, 0)
        }

