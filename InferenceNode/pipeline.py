from __future__ import annotations
import sys
import os
import threading
import uuid
import time
import json
import cv2
from typing import Dict, Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frame_source import FrameSourceFactory
from InferenceEngine import InferenceEngineFactory
from frame_source.video_capture_base import VideoCaptureBase
from InferenceEngine.engines.base_engine import BaseInferenceEngine
from ResultPublisher import ResultPublisher
from ResultPublisher.result_destinations import MQTTDestination


class InferencePipeline:
    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.nodes = []
        self.source : VideoCaptureBase
        self.inference_engine : BaseInferenceEngine
        self.result_publisher : ResultPublisher
        self._stop_requested = False  # Flag to control pipeline execution
        self._latest_frame = None  # Store latest processed frame for streaming
        self._inference_enabled = True  # Flag to enable/disable inference processing

        self._frame_lock = threading.Lock()  # Thread-safe access to latest frame

        self._frame_counter = 0  # Count processed frames
        self._inference_counter = 0  # Count inferences performed
        self._start_time = 0  # Record the start time
        
        # FPS calculation over rolling 10-second window
        self._frame_timestamps = []  # Store timestamps of processed frames
        self._fps_window_seconds = 10  # Calculate FPS over last 10 seconds
        
        # Latency tracking over rolling window
        self._inference_latencies = []  # Store inference latencies in milliseconds
        self._latency_window_size = 100  # Keep last 100 inference times for rolling average
        
        # Frame source configuration for auto-delete functionality
        self._frame_source_config = None
        self._current_image_path = None  # Track current image path for deletion
        
        # Thumbnail support
        self._thumbnail_captured = False  # Flag to track if thumbnail has been captured
        self._thumbnail_path = None  # Path to saved thumbnail image
        
        # Pipeline state tracking
        self._is_initialized = False  # True when configured and model is loaded
        self._is_running = False  # True when pipeline thread is actively running
        self._error_state = None  # None if no error, otherwise contains error message
        self._is_streaming = False  # True when streaming is active

    def __str__(self) -> str:
        return f"InferencePipeline(id={self.id}, source={self.source}, inference_engine={self.inference_engine}, result_publisher={self.result_publisher})"

    def get_state(self) -> Dict[str, Any]:
        """Get the current state of the pipeline
        
        Returns:
            Dictionary with state information:
            - initialized: bool - True if pipeline is configured and model loaded
            - running: bool - True if pipeline thread is actively processing frames
            - error: str or None - Error message if in error state
            - status: str - Combined status string (e.g., 'initialized_running', 'initialized_stopped')
        """
        # Determine combined status string
        if self._error_state:
            status = f"{'initialized' if self._is_initialized else 'uninitialized'}_error"
        elif self._is_running:
            status = "initialized_running"  # Can only run if initialized
        elif self._is_initialized:
            status = "initialized_stopped"
        else:
            status = "uninitialized_stopped"
        
        return {
            'initialized': self._is_initialized,
            'running': self._is_running,
            'error': self._error_state,
            'status': status
        }
    
    def is_initialized(self) -> bool:
        """Check if pipeline is initialized (configured and model loaded)"""
        return self._is_initialized
    
    def is_running(self) -> bool:
        """Check if pipeline is currently running"""
        return self._is_running
    
    def has_error(self) -> bool:
        """Check if pipeline is in error state"""
        return self._error_state is not None
    
    def get_error(self) -> Optional[str]:
        """Get the error message if pipeline is in error state"""
        return self._error_state
    
    def clear_error(self):
        """Clear the error state"""
        self._error_state = None

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get the current metrics of the pipeline.
        """
        if self._start_time == 0:
            self._start_time = time.perf_counter()

        current_time = time.perf_counter()
        elapsed_time = current_time - self._start_time
        
        # Calculate FPS over the last 10 seconds
        fps_10sec = self._calculate_rolling_fps(current_time)
        
        # Calculate rolling average inference latency
        avg_latency = self._calculate_rolling_latency()
        
        # Format uptime as human-readable string
        uptime_formatted = self._format_uptime(elapsed_time)
        
        # Get current state
        state = self.get_state()
        
        return {
            "id": self.id,
            "frame_count": self._frame_counter,
            "inference_count": self._inference_counter,
            "elapsed_time": elapsed_time,
            "uptime": uptime_formatted,  # Human-readable uptime
            "fps": fps_10sec,  # Use 10-second rolling average
            "fps_overall": self._frame_counter / elapsed_time if elapsed_time > 0 else 0,  # Overall FPS since start
            "inference_enabled": self._inference_enabled,
            "latency_ms": avg_latency,  # Rolling average inference latency in milliseconds
            "state": state,  # Include pipeline state information
            "initialized": state['initialized'],
            "running": state['running'],
            "error": state['error'],
        }
    
    def _calculate_rolling_fps(self, current_time: float) -> float:
        """
        Calculate FPS over the last 10 seconds using a rolling window.
        """
        # Remove timestamps older than the window
        cutoff_time = current_time - self._fps_window_seconds
        self._frame_timestamps = [ts for ts in self._frame_timestamps if ts >= cutoff_time]
        
        # Need at least 2 frames to calculate FPS
        if len(self._frame_timestamps) < 2:
            return 0.0
        
        # Calculate FPS based on frames in the window
        time_span = self._frame_timestamps[-1] - self._frame_timestamps[0]
        if time_span > 0:
            # Use len() - 1 because we're counting intervals between frames
            fps = (len(self._frame_timestamps) - 1) / time_span
            return round(fps, 1)  # Round to 1 decimal place for cleaner display
        else:
            # If all frames happened at the same time, can't calculate meaningful FPS
            return 0.0

    def _calculate_rolling_latency(self) -> float:
        """
        Calculate average inference latency over the last N inferences.
        """
        if not self._inference_latencies:
            return 0.0
        
        # Calculate average latency from the rolling window
        avg_latency = sum(self._inference_latencies) / len(self._inference_latencies)
        return round(avg_latency, 1)  # Round to 1 decimal place

    def _format_uptime(self, elapsed_seconds: float) -> str:
        """
        Format elapsed time into a human-readable uptime string.
        """
        if elapsed_seconds < 60:
            return f"{int(elapsed_seconds)}s"
        elif elapsed_seconds < 3600:  # Less than 1 hour
            minutes = int(elapsed_seconds // 60)
            seconds = int(elapsed_seconds % 60)
            return f"{minutes}m {seconds}s"
        elif elapsed_seconds < 86400:  # Less than 1 day
            hours = int(elapsed_seconds // 3600)
            minutes = int((elapsed_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:  # 1 day or more
            days = int(elapsed_seconds // 86400)
            hours = int((elapsed_seconds % 86400) // 3600)
            return f"{days}d {hours}h"

    def disable_publisher(self, id: str = 'all'):
        """Disable a specific result publisher by ID or all publishers"""
        print(f"DEBUG: disable_publisher called with id='{id}'")
        if id == 'all':
            for rp in self.result_publisher.destinations:
                rp.enabled = False
            print(f"Pipeline {self.id}: Disabled all result publishers")
            return

        if self.result_publisher:
            print(f"DEBUG: Looking for publisher with id='{id}' among {len(self.result_publisher.destinations)} destinations")
            for i, dest in enumerate(self.result_publisher.destinations):
                print(f"DEBUG: Destination {i}: _id='{getattr(dest, '_id', 'NO_ID')}', enabled={getattr(dest, 'enabled', 'NO_ENABLED')}")
            
            rp = self.result_publisher.get_by_id(id)
            if rp:
                rp.enabled = False
                print(f"Pipeline {self.id}: Disabled publisher {id} - new enabled state: {rp.enabled}")
            else:
                print(f"Pipeline {self.id}: Publisher {id} not found")
        else:
            print(f"Pipeline {self.id}: No result publisher configured")

    def enable_publisher(self, id: str = 'all'):
        """Enable a specific result publisher by ID or all publishers"""
        print(f"DEBUG: enable_publisher called with id='{id}'")
        if id == 'all':
            for rp in self.result_publisher.destinations:
                rp.enabled = True
                # Reset frame count if paused
                if hasattr(rp, 'frame_limit_reached') and rp.frame_limit_reached:
                    if hasattr(rp, 'reset_frame_count'):
                        rp.reset_frame_count()
                        print(f"Pipeline {self.id}: Reset frame count for paused publisher")
            print(f"Pipeline {self.id}: Enabled all result publishers")
            return

        if self.result_publisher:
            print(f"DEBUG: Looking for publisher with id='{id}' among {len(self.result_publisher.destinations)} destinations")
            for i, dest in enumerate(self.result_publisher.destinations):
                print(f"DEBUG: Destination {i}: _id='{getattr(dest, '_id', 'NO_ID')}', enabled={getattr(dest, 'enabled', 'NO_ENABLED')}")
            
            rp = self.result_publisher.get_by_id(id)
            if rp:
                # Reset frame count if paused (when re-enabling via UI toggle)
                if hasattr(rp, 'frame_limit_reached') and rp.frame_limit_reached:
                    if hasattr(rp, 'reset_frame_count'):
                        rp.reset_frame_count()
                        print(f"Pipeline {self.id}: Reset frame count for paused publisher {id}")
                
                rp.enabled = True
                print(f"Pipeline {self.id}: Enabled publisher {id} - new enabled state: {rp.enabled}")
            else:
                print(f"Pipeline {self.id}: Publisher {id} not found")
        else:
            print(f"Pipeline {self.id}: No result publisher configured")

    def get_publisher_states(self) -> Dict[str, Any]:
        """Get the current state of all publishers"""
        try:
            if not self.result_publisher:
                return {}
            
            states = {}
            
            for i, destination in enumerate(self.result_publisher.destinations):
                try:
                    if hasattr(destination, '_id'):
                        dest_id = str(destination._id)  # Ensure ID is string
                        
                        # Get attributes with type safety for JSON serialization
                        enabled = bool(getattr(destination, 'enabled', True))
                        dest_type = str(getattr(destination, 'type', 'unknown'))
                        is_configured = bool(getattr(destination, 'is_configured', False))
                        
                        # Ensure failure_count is always an integer
                        failure_count = getattr(destination, 'failure_count', 0)
                        
                        if not isinstance(failure_count, int):
                            try:
                                failure_count = int(failure_count) if str(failure_count).isdigit() else 0
                            except (ValueError, TypeError):
                                failure_count = 0
                        
                        # Get auto_disabled safely as boolean
                        try:
                            auto_disabled = bool(getattr(destination, 'auto_disabled', False))
                        except Exception:
                            auto_disabled = False
                        
                        # Get paused state (frame limit reached)
                        try:
                            is_paused = bool(getattr(destination, 'is_paused', False))
                        except Exception:
                            is_paused = False
                        
                        # Get frame count information
                        frame_count = int(getattr(destination, 'frame_count', 0))
                        max_frames = getattr(destination, 'max_frames', None)
                        if max_frames is not None:
                            try:
                                max_frames = int(max_frames)
                            except (ValueError, TypeError):
                                max_frames = None
                        
                        # Get last_error as string or None
                        last_error = getattr(destination, 'last_error', None)
                        if last_error is not None:
                            last_error = str(last_error)
                        
                        # Create the state dictionary with JSON-safe types
                        state_dict = {
                            'enabled': enabled,
                            'type': dest_type,
                            'configured': is_configured,
                            'failure_count': failure_count,
                            'auto_disabled': auto_disabled,
                            'is_paused': is_paused,
                            'frame_count': frame_count,
                            'max_frames': max_frames,
                            'last_error': last_error
                        }
                        
                        # Test JSON serialization of this state to catch issues early
                        try:
                            import json
                            json.dumps(state_dict)
                            states[dest_id] = state_dict
                        except Exception:
                            # Skip this destination to prevent the entire API from failing
                            pass
                            
                except Exception:
                    # Skip problematic destinations
                    pass
            
            # Test JSON serialization of the entire states dictionary
            try:
                import json
                json.dumps(states)
            except Exception:
                return {}  # Return empty dict if serialization fails
            
            return states
            
        except Exception:
            return {}


    def enable_inference(self):
        """Enable inference processing"""
        self._inference_enabled = True
        print(f"Pipeline {self.id}: Inference enabled")

    def disable_inference(self):
        """Disable inference processing"""
        self._inference_enabled = False
        print(f"Pipeline {self.id}: Inference disabled")

    def _should_auto_delete_images(self) -> bool:
        """Check if auto-delete is enabled for image folder sources"""
        if not self._frame_source_config:
            return False
        
        # Check if this is an image folder source with auto-delete enabled
        capture_type = self._frame_source_config.get('capture_type', '')
        auto_delete = self._frame_source_config.get('auto_delete', False)
        
        return capture_type in ['folder', 'image_folder'] and auto_delete
    
    def _is_folder_source(self) -> bool:
        """Check if this is a folder-based frame source"""
        if not self._frame_source_config:
            return False
        
        # Check if this is a folder source that should watch for new files
        capture_type = self._frame_source_config.get('capture_type', '')
        return capture_type in ['folder', 'image_folder']
    
    def _delete_current_image(self):
        """Delete the current image file if auto-delete is enabled"""
        if not self._should_auto_delete_images():
            return
            
        # Try to get the current file path from the frame source
        if hasattr(self.source, 'get_current_file_path'):
            try:
                current_file = self.source.get_current_file_path() # type: ignore
                if current_file and os.path.exists(current_file):
                    # Add pipeline ID to help identify which instance is deleting files
                    print(f"Pipeline {self.id}: Auto-deleting processed image: {current_file}")
                    os.remove(current_file)
                    print(f"Pipeline {self.id}: Successfully deleted: {current_file}")
            except FileNotFoundError:
                # File already deleted by another process/thread - this is expected in multi-instance scenarios
                print(f"Pipeline {self.id}: File already deleted (by another instance?): {getattr(self.source, 'get_current_file_path', lambda: 'unknown')()}")
            except Exception as e:
                print(f"Pipeline {self.id}: Error deleting image file: {e}")
        elif hasattr(self.source, 'current_file'):
            # Alternative attribute name
            try:
                current_file = self.source.current_file # type: ignore
                if current_file and os.path.exists(current_file):
                    # Add pipeline ID to help identify which instance is deleting files
                    print(f"Pipeline {self.id}: Auto-deleting processed image: {current_file}")
                    os.remove(current_file)
                    print(f"Pipeline {self.id}: Successfully deleted: {current_file}")
            except FileNotFoundError:
                # File already deleted by another process/thread - this is expected in multi-instance scenarios
                print(f"Pipeline {self.id}: File already deleted (by another instance?): {getattr(self.source, 'current_file', 'unknown')}")
            except Exception as e:
                print(f"Pipeline {self.id}: Error deleting image file: {e}")

    def is_inference_enabled(self) -> bool:
        """Check if inference is enabled"""
        return self._inference_enabled
    
    def set_confidence_threshold(self, threshold: float) -> bool:
        """Set the confidence threshold for the inference engine
        
        Args:
            threshold: Confidence threshold value (0.0 to 1.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not 0.0 <= threshold <= 1.0:
                print(f"Pipeline {self.id}: Invalid confidence threshold {threshold}, must be between 0.0 and 1.0")
                return False
            
            if self.inference_engine and hasattr(self.inference_engine, 'set_confidence_threshold'):
                self.inference_engine.set_confidence_threshold(threshold)
                print(f"Pipeline {self.id}: Confidence threshold set to {threshold}")
                return True
            else:
                print(f"Pipeline {self.id}: Inference engine does not support confidence threshold")
                return False
        except Exception as e:
            print(f"Pipeline {self.id}: Error setting confidence threshold: {e}")
            return False
    
    def get_confidence_threshold(self) -> Optional[float]:
        """Get the current confidence threshold from the inference engine
        
        Returns:
            float: Current confidence threshold, or None if not available
        """
        try:
            if self.inference_engine and hasattr(self.inference_engine, 'get_confidence_threshold'):
                return self.inference_engine.get_confidence_threshold()
            return None
        except Exception as e:
            print(f"Pipeline {self.id}: Error getting confidence threshold: {e}")
            return None
    
    def set_thumbnail_path(self, thumbnail_dir: str):
        """Set the directory where thumbnails will be saved"""
        if not os.path.exists(thumbnail_dir):
            os.makedirs(thumbnail_dir, exist_ok=True)
        self._thumbnail_path = os.path.join(thumbnail_dir, f"thumbnail_{self.id}.jpg")
    
    def capture_thumbnail(self, frame):
        """Capture a thumbnail from the current frame"""
        if self._thumbnail_path and frame is not None:
            try:
                # Resize frame to thumbnail size (e.g., 320x240) for faster loading
                height, width = frame.shape[:2]
                thumbnail_width = 320
                thumbnail_height = int((thumbnail_width / width) * height)
                
                # Resize the frame
                thumbnail = cv2.resize(frame, (thumbnail_width, thumbnail_height))
                
                # Save the thumbnail
                cv2.imwrite(self._thumbnail_path, thumbnail)
                self._thumbnail_captured = True
                print(f"Pipeline {self.id}: Thumbnail captured and saved to {self._thumbnail_path}")
                return True
            except Exception as e:
                print(f"Pipeline {self.id}: Failed to capture thumbnail: {e}")
                return False
        return False
    
    def get_thumbnail_path(self) -> Optional[str]:
        """Get the path to the thumbnail image"""
        if self._thumbnail_path and os.path.exists(self._thumbnail_path):
            return self._thumbnail_path
        return None
    
    def has_thumbnail(self) -> bool:
        """Check if a thumbnail exists for this pipeline"""
        return bool(self._thumbnail_path and os.path.exists(self._thumbnail_path))
    
    def delete_thumbnail(self):
        """Delete the thumbnail file"""
        if self._thumbnail_path and os.path.exists(self._thumbnail_path):
            try:
                os.remove(self._thumbnail_path)
                self._thumbnail_captured = False
                print(f"Pipeline {self.id}: Thumbnail deleted")
            except Exception as e:
                print(f"Pipeline {self.id}: Failed to delete thumbnail: {e}")

    def run(self):
        """
        Run the inference pipeline.
        """
        # if not self.source or not self.inference_engine:
            # raise ValueError("Pipeline is not properly configured.")

        print(f"Pipeline {self.id}: Starting run loop with frame source type: {type(self.source).__name__}")
        
        # Mark as running
        self._is_running = True
        self._error_state = None  # Clear any previous errors
        
        try:
            self.source.connect()
            print(f"Pipeline {self.id}: Frame source connected successfully")
            # Start the video capture
            # self.source.start_async()

            # For folder sources, we need to handle the case where the folder might be empty initially
            # but we still want to keep the pipeline running to watch for new files
            is_folder_source = self._is_folder_source()
            consecutive_empty_reads = 0
            max_empty_reads_before_sleep = 10  # After 10 consecutive empty reads, sleep briefly
            
            while not self._stop_requested:
                # Check if source is still connected, but for folder sources, don't exit immediately
                if not self.source.is_connected:
                    if is_folder_source:
                        # For folder sources, try to reconnect if disconnected
                        # print(f"Pipeline {self.id}: Folder source disconnected, attempting to reconnect...")
                        try:
                            self.source.connect()
                            if self.source.is_connected:
                                # print(f"Pipeline {self.id}: Folder source reconnected successfully")
                                consecutive_empty_reads = 0
                                continue
                            else:
                                # print(f"Pipeline {self.id}: Failed to reconnect folder source, will retry...")
                                time.sleep(1)  # Wait a bit before retrying
                                continue
                        except Exception as e:
                            # print(f"Pipeline {self.id}: Error reconnecting folder source: {e}")
                            time.sleep(1)  # Wait a bit before retrying
                            continue
                    else:
                        # For non-folder sources, exit when disconnected
                        # print(f"Pipeline {self.id}: Source disconnected, ending pipeline")
                        break
                
                success, frame = self.source.read()
                if not success or frame is None:
                    consecutive_empty_reads += 1
                    
                    if is_folder_source:
                # For folder sources, this is normal when there are no files yet
                        # Sleep briefly to avoid busy waiting, but keep the pipeline alive
                        if consecutive_empty_reads >= max_empty_reads_before_sleep:
                            # if consecutive_empty_reads == max_empty_reads_before_sleep:  # Log only once
                                # print(f"Pipeline {self.id}: No files in folder, entering wait mode...")
                            time.sleep(0.1)  # Brief sleep to reduce CPU usage
                            consecutive_empty_reads = 0  # Reset counter after sleep
                        continue
                    else:
                        # For other sources, continue as normal
                        continue
                
                # Reset consecutive empty reads counter when we get a frame
                consecutive_empty_reads = 0

                self._frame_counter += 1  # Increment frame counter
                
                # Record timestamp for FPS calculation
                current_time = time.perf_counter()
                self._frame_timestamps.append(current_time)
                
                # Clean up old timestamps every 100 frames to avoid doing it too frequently
                if self._frame_counter % 100 == 0:
                    cutoff_time = current_time - (self._fps_window_seconds + 2)  # +2 seconds buffer
                    self._frame_timestamps = [ts for ts in self._frame_timestamps if ts >= cutoff_time]

                # Run inference only if enabled
                results = None
                if self._inference_enabled:
                    # Measure inference latency
                    inference_start_time = time.perf_counter()
                    results = self.inference_engine.infer(frame)
                    inference_end_time = time.perf_counter()
                    
                    # Calculate latency in milliseconds
                    latency_ms = (inference_end_time - inference_start_time) * 1000
                    
                    # Add to rolling latency window
                    self._inference_latencies.append(latency_ms)
                    
                    # Keep only the last N latencies for rolling average
                    if len(self._inference_latencies) > self._latency_window_size:
                        self._inference_latencies.pop(0)
                    
                    self._inference_counter += 1  # Increment inference counter
                
                if results is not None:  # Check if results is not None
                    json_results = self.inference_engine.result_to_json(results)
                    # print(json_results)

                    if self.result_publisher.do_any_destinations_need_result_image() or self._is_streaming:
                        # Draw results on frame and store for streaming or publishing
                        with self._frame_lock:
                            output = self.inference_engine.draw(frame, results)
                            self._latest_frame = output.copy()
                        
                            # Capture thumbnail on first successful inference (with drawn results)
                            if not self._thumbnail_captured and self._thumbnail_path:
                                self.capture_thumbnail(output)
                    else:
                        # Store raw frame without drawing (for quick preview when streaming starts)
                        with self._frame_lock:
                            self._latest_frame = frame.copy()
                            
                            # Capture thumbnail on first successful frame if needed
                            if not self._thumbnail_captured and self._thumbnail_path:
                                self.capture_thumbnail(frame)
                else:
                    # If no results, store the original frame for streaming
                    with self._frame_lock:
                        self._latest_frame = frame.copy()
                        
                        # Capture thumbnail on first successful frame (original frame if no inference)
                        if not self._thumbnail_captured and self._thumbnail_path:
                            self.capture_thumbnail(frame)

                # Publish results only if we have them
                if results is not None:
                    #put json results in a Dict container like this Dict[str, Any]
                    to_publish = {"node_id": self.id, "results": json_results}

                    # Publish results
                    self.result_publisher.publish(to_publish, 
                                                  frame if self.result_publisher.do_any_destinations_need_image() else None,
                                                  self._latest_frame if self.result_publisher.do_any_destinations_need_result_image() else None)
                
                # Auto-delete the processed image if enabled
                self._delete_current_image()

        except Exception as e:
            print(f"Pipeline {self.id} error during execution: {e}")
            # Set error state
            self._error_state = str(e)
            # Disable inference when an error occurs to prevent further failures
            self._inference_enabled = False
            print(f"Pipeline {self.id}: Inference disabled due to error")
        finally:
            # Mark as not running
            self._is_running = False
            # Stop the video capture
            if hasattr(self, 'source') and self.source:
                self.source.stop()
            print(f"Pipeline {self.id} run loop ended")

    def configure(self, frame_source_config, inference_engine_config, result_publisher: ResultPublisher):

        self._frame_source_config = frame_source_config  # Store for auto-delete functionality
        # self.frame_source_config = frame_source_config
        self.source = FrameSourceFactory.create(**frame_source_config)

        self.inference_engine_config = inference_engine_config
        self.inference_engine = InferenceEngineFactory.create(**inference_engine_config)
        self.inference_engine.load()
        
        self.result_publisher = result_publisher
        
        # Mark as initialized once configuration is complete and model is loaded
        self._is_initialized = True
        self._error_state = None  # Clear any previous errors
        print(f"Pipeline {self.id}: Initialized successfully")

    def start(self):
        """
        Start the inference pipeline on a separate thread.
        """
        if not self._is_initialized:
            raise RuntimeError(f"Pipeline {self.id} cannot start - not initialized. Call configure() first.")
        
        if self._is_running:
            print(f"Pipeline {self.id} is already running")
            return
        
        self._start_time = time.perf_counter()  # Record the start time
        self._stop_requested = False  # Reset stop flag
        
        # Reset FPS tracking and counters
        self._frame_timestamps = []
        self._frame_counter = 0
        self._inference_counter = 0
        self._inference_latencies = []  # Reset latency tracking
        
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        """
        Stop the inference pipeline.
        """
        print(f"Stopping pipeline {self.id}")
        self._stop_requested = True  # Signal the run loop to stop
        self._is_streaming = False  # Reset streaming flag when pipeline stops
        
        # Update thumbnail with the last received frame before stopping
        if self._latest_frame is not None and self._thumbnail_path:
            try:
                with self._frame_lock:
                    last_frame = self._latest_frame.copy()
                self.capture_thumbnail(last_frame)
                print(f"Pipeline {self.id}: Updated thumbnail with last frame before stopping")
            except Exception as e:
                print(f"Pipeline {self.id}: Failed to update thumbnail with last frame: {e}")
        
        # Give the thread some time to stop gracefully
        if hasattr(self, 'thread') and self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)  # Wait up to 5 seconds
            if self.thread.is_alive():
                print(f"Warning: Pipeline {self.id} thread did not stop within timeout")
        
        # Ensure source is stopped
        if hasattr(self, 'source') and self.source:
            try:
                self.source.stop()
            except Exception as e:
                print(f"Error stopping source: {e}")
        
        # Mark as not running (thread will also set this in finally block)
        self._is_running = False
        
        print(f"Pipeline {self.id} stopped")

    def get_latest_frame(self):
        """Get the latest processed frame for streaming"""
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def start_streaming(self):
        """Enable streaming flag to indicate frames should be drawn with results"""
        self._is_streaming = True
        print(f"Pipeline {self.id}: Streaming enabled")

    def stop_streaming(self):
        """Disable streaming flag to optimize performance when not streaming"""
        self._is_streaming = False
        print(f"Pipeline {self.id}: Streaming disabled")

    def is_streaming(self) -> bool:
        """Check if streaming is currently active"""
        return self._is_streaming

    def __del__(self):
        try:
            self.stop()
            # Note: We do NOT delete thumbnails here - they should persist
            # across sessions and only be deleted when pipeline is explicitly deleted
        except Exception:
            pass  # Ignore errors during cleanup


def main():
    import cv2

    mqtt_destination = MQTTDestination()
    mqtt_destination.configure(server='192.168.1.241', port=1883, topic='inference/results', rate_limit=0.1)
    mqtt_destination.include_image_data = False  # Include image data in published messages
    
    result_publisher = ResultPublisher()
    result_publisher.add(mqtt_destination)

    frame_source_config = {'capture_type': 'webcam', 'source': 0, 'threaded': True, 'width': 640, 'height': 480, 'fps': 30}
    # frame_source_config = {'capture_type': 'realsense', 'width': 1280, 'height': 720, 'threaded': False, 'fps': 30}
    inference_config = {'engine_type': 'ultralytics', 'model_path': 'yolo11n-pose.pt', 'device': 'intel:cpu'}
    # inference_config = {'engine_type': 'geti', 'model_path': 'C:\\Users\\olive\\OneDrive\\Projects\\InferNode\\InferenceNode\\model_repository\\models\\Deployment-juggling-balls (1)_dd785c2f.zip', 'device': 'cpu'}


    pipeline = InferencePipeline()
    pipeline.configure(
        frame_source_config=frame_source_config,
        inference_engine_config=inference_config,
        result_publisher=result_publisher
    )

    print(pipeline)

    pipeline.start()

    while True:
        frame = pipeline.get_latest_frame()
        if frame is not None:
            cv2.imshow(f"Pipeline {pipeline.id}", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    pipeline.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()