import base64
import threading
import logging
import uuid
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import copy

import cv2
import numpy as np
from .result_destinations import BaseResultDestination

class ResultPublisher:
    """Main result publisher that manages multiple destinations"""
    
    def __init__(self, max_workers: int = 4):
        self.destinations: List[BaseResultDestination] = []
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = threading.Lock()
        # Thread pool for non-blocking publishing
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ResultPublisher")
        self._shutdown = False
    
    def add(self, destination: BaseResultDestination) -> str:
        """Add a result destination and return its ID"""
        with self._lock:
            # Use existing ID if available, otherwise generate a new one
            if hasattr(destination, '_id') and destination._id:
                destination_id = destination._id
            else:
                destination_id = str(uuid.uuid4())
                destination._id = destination_id  # Add ID attribute to destination
            
            self.destinations.append(destination)
            self.logger.info(f"Added destination: {destination.__class__.__name__} with ID: {destination_id}")
            return destination_id
    
    def remove(self, destination: BaseResultDestination) -> None:
        """Remove a result destination"""
        with self._lock:
            if destination in self.destinations:
                self.destinations.remove(destination)
                self.logger.info(f"Removed destination: {destination.__class__.__name__}")
    
    def remove_by_id(self, destination_id: str) -> bool:
        """Remove a destination by its ID"""
        with self._lock:
            for destination in self.destinations:
                if hasattr(destination, '_id') and str(destination._id) == str(destination_id):
                    self.destinations.remove(destination)
                    self.logger.info(f"Removed destination with ID: {destination_id}")
                    return True
            return False
    
    def get_by_id(self, destination_id: str) -> Optional[BaseResultDestination]:
        """Get a destination by its ID"""
        with self._lock:
            for destination in self.destinations:
                if hasattr(destination, '_id') and str(destination._id) == str(destination_id):
                    return destination
            return None
    
    def _publish_to_destination(self, destination: BaseResultDestination, data: Dict[str, Any]) -> bool:
        """Helper method to publish to a single destination"""
        try:
            return destination.publish(data)
        except Exception as e:
            self.logger.error(f"Error publishing to {destination.__class__.__name__}: {str(e)}")
            return False
        
    def do_any_destinations_need_image(self) -> bool:
        """Check if any destination needs image data"""
        with self._lock:
            return any(getattr(dest, 'enabled', True) and dest.include_image_data for dest in self.destinations)

    def do_any_destinations_need_result_image(self) -> bool:
        """Check if any destination needs result image data"""
        with self._lock:
            return any(getattr(dest, 'enabled', True) and dest.include_result_image for dest in self.destinations)

    def publish(self, data: Dict[str, Any], 
                original_image: Optional[np.ndarray] = None, 
                result_image: Optional[np.ndarray] = None) -> None:
        """Publish data to all configured destinations (non-blocking)"""
        if self._shutdown:
            self.logger.warning("Publisher is shutting down, ignoring publish request")
            return
        
        # Create a deep copy of data to avoid race conditions
        dest_data = copy.deepcopy(data)
        
        # Encode image once if any destination needs it
        encoded_image = None
        if original_image is not None:
            success, buffer = cv2.imencode('.jpg', original_image)
            if success:
                encoded_image = base64.b64encode(buffer.tobytes()).decode('utf-8')

        # Similarly encode result image if needed
        encoded_result_image = None
        if result_image is not None:
            success, buffer = cv2.imencode('.jpg', result_image)
            if success:
                encoded_result_image = base64.b64encode(buffer.tobytes()).decode('utf-8')

        # Submit publishing tasks to thread pool
        with self._lock:
            # Only publish to enabled destinations that are not paused
            enabled_destinations = [dest for dest in self.destinations 
                                  if getattr(dest, 'enabled', True) and not getattr(dest, 'is_paused', False)]
        
        for destination in enabled_destinations:
            # Prepare data for this destination
            if encoded_image is not None and destination.include_image_data:
                dest_data["image"] = encoded_image

            if encoded_result_image is not None and destination.include_result_image:
                dest_data["result_image"] = encoded_result_image
            
            # Submit to thread pool
            future = self._executor.submit(self._publish_to_destination, destination, dest_data)
            
            # Optionally add a callback for logging results
            def log_result(fut, dest_name=destination.__class__.__name__):
                try:
                    success = fut.result()
                    if not success:
                        self.logger.debug(f"Failed to publish to {dest_name}")
                except Exception as e:
                    self.logger.error(f"Unexpected error in publishing task for {dest_name}: {str(e)}")
            
            future.add_done_callback(log_result)
    
    def get_destinations(self) -> List[str]:
        """Get list of configured destination types"""
        with self._lock:
            return [dest.__class__.__name__ for dest in self.destinations]
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """Shutdown the publisher and wait for pending tasks to complete"""
        self.logger.info("Shutting down ResultPublisher...")
        self._shutdown = True
        
        if wait:
            # Submit a dummy task to help with graceful shutdown timing
            try:
                self._executor.shutdown(wait=True)
            except Exception as e:
                self.logger.warning(f"Exception during executor shutdown: {e}")
        else:
            # Cancel pending futures and shutdown immediately
            try:
                # Try to cancel pending futures if supported
                self._executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # Fallback for older Python versions
                self._executor.shutdown(wait=False)
        
        self.logger.info("ResultPublisher shutdown complete")
    
    def clear(self) -> None:
        """Remove all destinations"""
        with self._lock:
            # Close any resources that need cleanup
            for destination in self.destinations:
                if hasattr(destination, 'close'):
                    try:
                        destination.close()
                    except Exception as e:
                        self.logger.error(f"Error closing {destination.__class__.__name__}: {str(e)}")
            
            self.destinations.clear()
            self.logger.info("All destinations cleared")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures proper cleanup"""
        self.shutdown(wait=True)
