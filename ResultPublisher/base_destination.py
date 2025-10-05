import json
import time
import logging
import socket
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime


class BaseResultDestination(ABC):
    """Base class for all result destinations"""
    
    def __init__(self):
        self.type = self.__class__.__name__
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rate_limit = None
        self.last_publish_time = 0
        self.is_configured = False
        self._id: Optional[str] = None  # Unique identifier for this destination
        self.enabled = True  # Whether this destination is enabled
        self._lock = threading.Lock()  # Thread-safe lock for frame counting and state changes
        self.include_image_data = False  # Whether to include image data in the published results
        self.include_result_image = False  # Whether to include result image in the published results
        self.context_variables = {} # Context variables for substitution
        
        # Frame/call limit tracking
        self.max_frames = None  # Maximum number of frames/calls before auto-pause
        self.frame_count = 0  # Current count of published frames
        self.frame_limit_reached = False  # Whether frame limit has been reached (paused state)
        self._pause_warning_logged = False  # Flag to prevent spam logging when paused
        
        # Circuit breaker for automatic disabling on repeated failures
        self.failure_count = 0
        self.max_failures = 5  # Disable after 5 consecutive failures
        self.failure_threshold_reached = False
        self.last_failure_time = 0
        self.success_count_since_failure = 0
        self.last_error = None  # Last error message

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Get the configuration schema for this destination type.
        This defines what UI fields should be displayed and their validation rules.
        
        Returns:
            Dictionary defining the configuration schema
        """
        return {
            'fields': [
                {
                    'name': 'rate_limit',
                    'label': 'Rate Limit',
                    'type': 'number',
                    'min': 0,
                    'max': 1000,
                    'step': 0.1,
                    'placeholder': 'e.g., 1.0',
                    'description': 'Minimum seconds between messages (0 for unlimited)',
                    'required': False,
                    'default': None,
                    'unit': 'seconds',
                    'col_width': 6  # Display in half width column
                },
                {
                    'name': 'max_frames',
                    'label': 'Max Frames/Calls',
                    'type': 'number',
                    'min': 0,
                    'max': 1000000,
                    'step': 1,
                    'placeholder': 'e.g., 1000',
                    'description': 'Maximum number of frames to publish before auto-disabling (0 or empty for unlimited)',
                    'required': False,
                    'default': None,
                    'unit': 'frames',
                    'col_width': 6  # Display in half width column
                },
                {
                    'name': 'include_image_data',
                    'label': 'Include Image Data',
                    'type': 'checkbox',
                    'description': 'Include image data in published results',
                    'required': False,
                    'default': False,
                    'col_width': 6  # Display in half width column
                },
                {
                    'name': 'include_result_image',
                    'label': 'Include Result Image',
                    'type': 'checkbox',
                    'description': 'Include result image in published results',
                    'required': False,
                    'default': False,
                    'col_width': 6  # Display in half width column
                }
            ]
        }

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        if self.failure_threshold_reached:
            status += " (auto-disabled due to failures)"
        if self.frame_limit_reached:
            status += " (paused: frame limit reached)"
        frame_info = f", frames={self.frame_count}"
        if self.max_frames:
            frame_info += f"/{self.max_frames}"
        return f"BaseResultDestination(type={self.type}, id={self._id}, is_configured={self.is_configured}, status={status}, failures={self.failure_count}{frame_info})"
    
    @property
    def auto_disabled(self) -> bool:
        """Check if this destination was auto-disabled due to failures (not frame limit pause)"""
        return self.failure_threshold_reached
    
    @property
    def is_paused(self) -> bool:
        """Check if this destination is paused due to frame limit"""
        return self.frame_limit_reached

    def _record_failure(self, error_msg: str = "") -> None:
        """Record a failure and potentially auto-disable the destination"""
        self.failure_count += 1
        self.success_count_since_failure = 0
        self.last_failure_time = time.time()
        
        # Ensure types are integers (defensive programming)
        if not isinstance(self.failure_count, int):
            self.failure_count = int(self.failure_count) if str(self.failure_count).isdigit() else 0
        if not isinstance(self.max_failures, int):
            self.max_failures = int(self.max_failures) if str(self.max_failures).isdigit() else 5
        
        if self.failure_count >= self.max_failures and not self.failure_threshold_reached:
            self.failure_threshold_reached = True
            self.enabled = False
            self.logger.warning(f"Auto-disabling destination after {self.max_failures} consecutive failures. "
                              f"Last error: {error_msg}. Re-enable manually or via API when issue is resolved.")
        elif self.failure_count < self.max_failures:
            self.logger.debug(f"Failure {self.failure_count}/{self.max_failures}: {error_msg}")

    def _record_success(self) -> None:
        """Record a successful publish and potentially reset failure count"""
        self.success_count_since_failure += 1
        
        # Ensure types are integers (defensive programming)
        if not isinstance(self.success_count_since_failure, int):
            self.success_count_since_failure = int(self.success_count_since_failure) if str(self.success_count_since_failure).isdigit() else 0
        if not isinstance(self.failure_count, int):
            self.failure_count = int(self.failure_count) if str(self.failure_count).isdigit() else 0
        
        # Reset failure count after some successful publishes
        if self.success_count_since_failure >= 3 and self.failure_count > 0:
            self.logger.info(f"Resetting failure count after {self.success_count_since_failure} successful publishes")
            self.failure_count = 0
            self.success_count_since_failure = 0
            
            # If this destination was auto-disabled, we don't automatically re-enable it
            # User should manually re-enable it to confirm the issue is resolved
            if self.failure_threshold_reached:
                self.logger.info("Destination was auto-disabled due to failures. Please manually re-enable when ready.")

    def reset_failure_count(self) -> None:
        """Manually reset failure count and re-enable if auto-disabled"""
        self.failure_count = 0
        self.success_count_since_failure = 0
        self.failure_threshold_reached = False
        if not self.enabled and self.is_configured:
            self.enabled = True
            self.logger.info("Destination manually re-enabled and failure count reset")
    
    def reset_frame_count(self) -> None:
        """Manually reset frame count and unpause if paused due to frame limit"""
        self.frame_count = 0
        self.frame_limit_reached = False
        self._pause_warning_logged = False
        self.logger.info("Destination frame count reset and unpaused")
    
    def set_max_frames(self, max_frames: Optional[int]) -> None:
        """Set maximum number of frames before auto-disable (None or 0 for unlimited)"""
        if max_frames is not None and max_frames > 0:
            self.max_frames = int(max_frames)
        else:
            self.max_frames = None

    def set_context_variables(self, **kwargs) -> None:
        """Set context variables for string substitution"""
        self.context_variables.update(kwargs)
        self.logger.debug(f"Context variables updated: {self.context_variables}")

    def get_available_variables(self, additional_vars: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get all available variables for substitution (useful for debugging)"""
        now = datetime.utcnow()
        variables = {
            # Time-based variables (always available)
            'timestamp': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'unix_time': str(int(time.time())),
            'hostname': socket.gethostname(),
            
            # Default values for common variables
            'node_id': 'unknown-node',
            'node_name': 'InferNode',
            'pipeline_id': 'unknown-pipeline',
            'model_name': 'unknown-model'
        }
        
        # Override defaults with context variables
        if self.context_variables:
            variables.update(self.context_variables)
        
        # Add any additional variables passed to this call
        if additional_vars:
            variables.update(additional_vars)
            
        return variables

    def substitute_variables(self, text: str, additional_vars: Optional[Dict[str, Any]] = None) -> str:
        """
        Substitute variables in text using format like {variable_name}
        
        Supported variables:
        - {node_id}: Node identifier
        - {node_name}: Node name
        - {hostname}: System hostname
        - {timestamp}: Current timestamp (ISO format)
        - {date}: Current date (YYYY-MM-DD)
        - {time}: Current time (HH:MM:SS)
        - {unix_time}: Unix timestamp
        - Any custom variables set via set_context_variables()
        """
        if not text:
            return text
            
        # Build substitution variables with defaults
        now = datetime.utcnow()
        variables = {
            # Time-based variables (always available)
            'timestamp': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'unix_time': str(int(time.time())),
            'hostname': socket.gethostname(),
            
            # Default values for common variables
            'node_id': 'unknown-node',
            'node_name': 'InferNode',
            'pipeline_id': 'unknown-pipeline',
            'model_name': 'unknown-model'
        }
        
        # Override defaults with context variables
        if self.context_variables:
            variables.update(self.context_variables)
        
        # Add any additional variables passed to this call (highest priority)
        if additional_vars:
            variables.update(additional_vars)
        
        try:
            # Use str.format() for variable substitution
            return text.format(**variables)
        except KeyError as e:
            self.logger.warning(f"Variable substitution failed - unknown variable: {e}")
            return text
        except Exception as e:
            self.logger.warning(f"Variable substitution failed: {str(e)}")
            return text

    def set_rate_limit(self, rate_limit: Optional[float]) -> None:
        """Set rate limit as minimum seconds between publishes (0 or None for unlimited)"""
        self.rate_limit = rate_limit
    
    def can_publish(self) -> bool:
        """Check if enough time has passed since last publish (based on rate_limit in seconds) and if destination is enabled"""
        try:
            if not self.enabled:
                return False
            
            # Check if paused due to frame limit
            if self.frame_limit_reached:
                return False
                
            if self.rate_limit is None:
                return True
            
            # Ensure types are numeric (defensive programming)
            current_time = time.time()
            rate_limit = float(self.rate_limit) if self.rate_limit is not None else 0
            last_publish_time = float(self.last_publish_time) if self.last_publish_time is not None else 0
            
            return (current_time - last_publish_time) >= rate_limit
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Type error in can_publish comparison: {e}, defaulting to allow publish")
            return True
    
    def publish(self, data: Dict[str, Any]) -> bool:
        """Publish data to destination with rate limiting and enabled check"""
        if not self.enabled:
            if not self.failure_threshold_reached:
                self.logger.debug("Destination disabled, skipping publish")
            # Don't log if auto-disabled to avoid spam
            return False
        
        if not self.is_configured:
            self._record_failure("Destination not configured")
            return False
        
        # Thread-safe rate limit and frame limit check - CRITICAL SECTION
        with self._lock:
            # Check if paused due to frame limit
            if self.frame_limit_reached:
                # Silently skip - user can unpause by toggling the destination
                # Don't log to avoid spam (warning already logged when paused)
                return False
            
            # Check rate limit atomically with last_publish_time update
            if self.rate_limit is not None:
                current_time = time.time()
                rate_limit = float(self.rate_limit)
                last_publish_time = float(self.last_publish_time) if self.last_publish_time is not None else 0
                
                if (current_time - last_publish_time) < rate_limit:
                    self.logger.debug("Rate limit exceeded, skipping publish")
                    return False
            
            # Update last_publish_time BEFORE publishing to prevent race condition
            # This ensures that if another thread checks can_publish() now, it will see the updated time
            self.last_publish_time = time.time()
        
        # Now do the actual publish (outside the lock to allow concurrent publishes to different destinations)
        try:
            result = self._publish(data)
            if result:
                self._record_success()
                
                # Thread-safe frame count increment and limit check
                with self._lock:
                    self.frame_count += 1
                    if self.max_frames is not None and self.frame_count >= self.max_frames:
                        self.frame_limit_reached = True
                        # Only log warning once when transitioning to paused state
                        if not self._pause_warning_logged:
                            self.logger.warning(f"Frame limit reached ({self.max_frames} frames). Destination paused. "
                                              f"Toggle the destination off/on in the UI to reset and continue.")
                            self._pause_warning_logged = True
                
                return True
            else:
                # Revert last_publish_time if publish failed
                with self._lock:
                    self.last_publish_time = 0
                self._record_failure("Publish method returned False")
                return False
        except Exception as e:
            # Revert last_publish_time if publish failed
            with self._lock:
                self.last_publish_time = 0
            error_msg = f"Failed to publish: {str(e)}"
            self._record_failure(error_msg)
            return False
    
    def configure_common(self, rate_limit: Optional[float] = None, 
                        max_frames: Optional[int] = None,
                        include_image_data: bool = False,
                        include_result_image: bool = False, **kwargs) -> None:
        """
        Configure common destination parameters. 
        Call this from subclass configure() methods to handle common parameters.
        
        Args:
            rate_limit: Minimum seconds between publishes (None or 0 for unlimited)
            max_frames: Maximum frames before auto-pause (None or 0 for unlimited)
            include_image_data: Whether to include image data in published results
            include_result_image: Whether to include result image in published results
            **kwargs: Additional subclass-specific parameters (ignored here)
        """
        self.include_image_data = include_image_data
        self.include_result_image = include_result_image
        self.set_rate_limit(rate_limit)
        self.set_max_frames(max_frames)
    
    @abstractmethod
    def configure(self, **kwargs) -> None:
        """Configure the destination"""
        pass
    
    @abstractmethod
    def _publish(self, data: Dict[str, Any]) -> bool:
        """Actual publish implementation"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the destination"""
        pass