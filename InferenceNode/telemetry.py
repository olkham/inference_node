import json
import time
import uuid
import psutil
import platform
import threading
import logging
from typing import Dict, Any, Optional
from datetime import datetime

class NodeTelemetry:
    """Handles node telemetry collection and publishing"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.logger = logging.getLogger(self.__class__.__name__)
        self.running = False
        self.telemetry_thread = None
        self.mqtt_client = None
        self.mqtt_topic = None
        self.mqtt_server = None
        self.mqtt_port = 1883
        self.update_interval = 5.0  # seconds
        
    def configure_mqtt(self, mqtt_server: str, mqtt_topic: str, 
                      mqtt_port: int = 1883, mqtt_username: Optional[str] = None,
                      mqtt_password: Optional[str] = None):
        """Configure MQTT for telemetry publishing"""
        try:
            import paho.mqtt.client as mqtt
            
            # Store configuration
            self.mqtt_server = mqtt_server
            self.mqtt_port = mqtt_port
            self.mqtt_topic = mqtt_topic
            
            self.mqtt_client = mqtt.Client()
            
            if mqtt_username and mqtt_password:
                self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
            
            self.mqtt_client.connect(mqtt_server, mqtt_port, 60)
            self.mqtt_client.loop_start()
            
            self.logger.info(f"MQTT telemetry configured: {mqtt_server}:{mqtt_port}/{mqtt_topic}")
            
        except ImportError:
            self.logger.error("paho-mqtt package not installed for telemetry")
        except Exception as e:
            self.logger.error(f"MQTT telemetry configuration failed: {str(e)}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Collect system information"""
        try:
            # CPU information
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get CPU temperature if available
            cpu_temp = self._get_cpu_temperature()
            
            # Memory information
            memory = psutil.virtual_memory()
            
            # Disk information
            disk = psutil.disk_usage('/')
            
            # Network information
            network = psutil.net_io_counters()
            
            # GPU information (basic)
            gpu_info = self._get_gpu_info()
            
            return {
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "system": {
                    "platform": self._parse_windows_platform(platform.platform()),
                    "platform_raw": platform.platform(),
                    "processor": platform.processor(),
                    "architecture": platform.architecture()[0]
                },
                "cpu": {
                    "count": cpu_count,
                    "frequency_mhz": cpu_freq.current if cpu_freq else None,
                    "usage_percent": cpu_percent,
                    "temperature_c": cpu_temp
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "usage_percent": round((disk.used / disk.total) * 100, 2)
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv
                },
                "gpu": gpu_info
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting system info: {str(e)}")
            return {
                "node_id": self.node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information if available"""
        gpu_info = {"available": False}
        
        # Try NVIDIA GPU first with the new library
        try:
            import nvidia_ml_py as nvml
            nvml.nvmlInit()
            device_count = nvml.nvmlDeviceGetCount()
            
            gpus = []
            for i in range(device_count):
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                name = nvml.nvmlDeviceGetName(handle).decode('utf-8')
                memory_info = nvml.nvmlDeviceGetMemoryInfo(handle)
                
                # Get additional info if available
                try:
                    utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
                    temperature = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                    power = nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert mW to W
                except:
                    utilization = None
                    temperature = None
                    power = None
                
                gpu_data = {
                    "id": i,
                    "name": name,
                    "memory_total_gb": round(memory_info.total / (1024**3), 2),
                    "memory_used_gb": round(memory_info.used / (1024**3), 2),
                    "memory_free_gb": round(memory_info.free / (1024**3), 2),
                    "vendor": "NVIDIA"
                }
                
                # Add optional metrics if available
                if utilization:
                    gpu_data["gpu_utilization_percent"] = utilization.gpu
                    gpu_data["memory_utilization_percent"] = utilization.memory
                if temperature:
                    gpu_data["temperature_c"] = temperature
                if power:
                    gpu_data["power_usage_w"] = round(power, 1)
                
                gpus.append(gpu_data)
            
            gpu_info = {"available": True, "devices": gpus, "driver_version": nvml.nvmlSystemGetDriverVersion().decode('utf-8')}
            
        except ImportError:
            # Try fallback to deprecated pynvml if nvidia-ml-py not available
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                
                gpus = []
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    
                    gpus.append({
                        "id": i,
                        "name": name,
                        "memory_total_gb": round(memory_info.total / (1024**3), 2),
                        "memory_used_gb": round(memory_info.used / (1024**3), 2),
                        "vendor": "NVIDIA"
                    })
                
                gpu_info = {"available": True, "devices": gpus}
                self.logger.warning("Using deprecated pynvml library. Consider installing nvidia-ml-py instead.")
                
            except ImportError:
                # No NVIDIA libraries available, try generic GPU detection
                gpu_info = self._get_generic_gpu_info()
            except Exception as e:
                self.logger.debug(f"Fallback GPU info collection failed: {str(e)}")
                gpu_info = self._get_generic_gpu_info()
                
        except Exception as e:
            self.logger.debug(f"NVIDIA GPU info collection failed: {str(e)}")
            # Try generic GPU detection as fallback
            gpu_info = self._get_generic_gpu_info()
        
        return gpu_info
    
    def _get_generic_gpu_info(self) -> Dict[str, Any]:
        """Get generic GPU information without NVIDIA-specific libraries"""
        try:
            # Try to get basic GPU info from system
            gpu_devices = []
            
            # On Linux, try reading from /proc or lspci if available
            if platform.system() == "Linux":
                try:
                    import subprocess
                    result = subprocess.run(['lspci', '-nn'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if 'VGA' in line or 'Display controller' in line:
                                # Extract GPU name from lspci output
                                parts = line.split(': ')
                                if len(parts) > 1:
                                    gpu_name = parts[1].split('[')[0].strip()
                                    gpu_devices.append({
                                        "name": gpu_name,
                                        "vendor": "Unknown",
                                        "memory_total_gb": "Unknown"
                                    })
                except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                    pass
            
            if gpu_devices:
                return {"available": True, "devices": gpu_devices, "detection_method": "generic"}
            else:
                return {"available": False, "message": "No GPU detection method available"}
                
        except Exception as e:
            self.logger.debug(f"Generic GPU detection failed: {str(e)}")
            return {"available": False, "message": "GPU detection failed"}
    
    def _parse_windows_platform(self, platform_string: str) -> str:
        """Parse Windows platform string to readable format"""
        try:
            # Windows version mapping
            windows_versions = {
                "6.1.7600": "Windows 7",
                "6.1.7601": "Windows 7 with Service Pack 1",
                "6.2.9200": "Windows 8",
                "6.3.9200": "Windows 8.1",
                "6.3.9600": "Windows 8.1 with Update 1",
                "10.0.10240": "Windows 10 Version 1507",
                "10.0.10586": "Windows 10 Version 1511 (November Update)",
                "10.0.14393": "Windows 10 Version 1607 (Anniversary Update)",
                "10.0.15063": "Windows 10 Version 1703 (Creators Update)",
                "10.0.16299": "Windows 10 Version 1709 (Fall Creators Update)",
                "10.0.17134": "Windows 10 Version 1803 (April 2018 Update)",
                "10.0.17763": "Windows 10 Version 1809 (October 2018 Update)",
                "10.0.18362": "Windows 10 Version 1903 (May 2019 Update)",
                "10.0.18363": "Windows 10 Version 1909 (November 2019 Update)",
                "10.0.19041": "Windows 10 Version 2004 (May 2020 Update)",
                "10.0.19042": "Windows 10 Version 20H2 (October 2020 Update)",
                "10.0.19043": "Windows 10 Version 21H1 (May 2021 Update)",
                "10.0.19044": "Windows 10 Version 21H2 (November 2021 Update)",
                "10.0.19045": "Windows 10 Version 22H2 (2022 Update)",
                "10.0.20348": "Windows Server 2022 Version 21H2",
                "10.0.22000": "Windows 11 Version 21H2 (original release)",
                "10.0.22621": "Windows 11 Version 22H2 (2022 Update)",
                "10.0.22631": "Windows 11 Version 23H2 (2023 Update)",
                "10.0.26100": "Windows 11 Version 24H2 (2024 Update)"
            }
            
            # Check if this is a Windows platform string
            if not platform_string.startswith("Windows"):
                return platform_string
            
            # Extract version number from platform string
            # Format: Windows-10-10.0.26100-SP0
            import re
            version_match = re.search(r'(\d+\.\d+\.\d+)', platform_string)
            
            if version_match:
                version = version_match.group(1)
                readable_version = windows_versions.get(version)
                
                if readable_version:
                    # Check if it's a server version based on platform string
                    if "Server" in platform_string or any(server_indicator in platform_string.lower() 
                                                         for server_indicator in ["datacenter", "standard", "enterprise"]):
                        # Handle server versions
                        if version == "6.1.7600" or version == "6.1.7601":
                            return "Windows Server 2008 R2" + (" with Service Pack 1" if version == "6.1.7601" else "")
                        elif version == "6.2.9200":
                            return "Windows Server 2012"
                        elif version == "6.3.9200" or version == "6.3.9600":
                            return "Windows Server 2012 R2"
                        elif version == "10.0.14393":
                            return "Windows Server 2016"
                        elif version == "10.0.17763":
                            return "Windows Server 2019"
                        elif version == "10.0.20348":
                            return "Windows Server 2022 Version 21H2"
                    
                    return readable_version
            
            # If no match found, return original string
            return platform_string
            
        except Exception as e:
            self.logger.debug(f"Platform parsing failed: {str(e)}")
            return platform_string
    
    def _get_cpu_temperature(self):
        """Get CPU temperature in Celsius"""
        try:
            # Check if sensors_temperatures is available (Linux/some systems)
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                
                if temps:
                    # Try common CPU temperature sensor names
                    cpu_sensors = ['coretemp', 'cpu_thermal', 'k10temp', 'zenpower']
                    
                    for sensor_name in cpu_sensors:
                        if sensor_name in temps:
                            sensor_list = temps[sensor_name]
                            if sensor_list:
                                # Get the first sensor reading (usually package temp)
                                temp = sensor_list[0].current
                                if temp and temp > 0:
                                    return round(temp, 1)
                    
                    # If no specific CPU sensors found, try the first available sensor
                    for sensor_name, sensor_list in temps.items():
                        if sensor_list:
                            temp = sensor_list[0].current
                            if temp and temp > 0:
                                return round(temp, 1)
            
            # Windows alternative using WMI (if available)
            if platform.system() == "Windows":
                try:
                    import wmi
                    w = wmi.WMI(namespace="root\\wmi")
                    temperature_infos = w.MSAcpi_ThermalZoneTemperature()
                    if temperature_infos:
                        # Convert from tenths of Kelvin to Celsius
                        temp_kelvin = temperature_infos[0].CurrentTemperature / 10.0
                        temp_celsius = temp_kelvin - 273.15
                        if temp_celsius > 0 and temp_celsius < 150:  # Sanity check
                            return round(temp_celsius, 1)
                except ImportError:
                    pass  # WMI not available
                except Exception:
                    pass  # WMI query failed
                        
        except Exception as e:
            self.logger.debug(f"CPU temperature collection failed: {str(e)}")
            
        return None
    
    def start_telemetry(self):
        """Start telemetry collection and publishing"""
        if self.running:
            return
            
        self.running = True
        self.telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.telemetry_thread.start()
        self.logger.info("Telemetry started")
    
    def stop_telemetry(self):
        """Stop telemetry collection"""
        self.running = False
        if self.telemetry_thread:
            self.telemetry_thread.join(timeout=5)
        self.logger.info("Telemetry stopped")
    
    def _telemetry_loop(self):
        """Main telemetry collection loop"""
        while self.running:
            try:
                telemetry_data = self.get_system_info()
                
                if self.mqtt_client and self.mqtt_topic:
                    message = json.dumps(telemetry_data)
                    self.mqtt_client.publish(self.mqtt_topic, message)
                    self.logger.debug("Telemetry published to MQTT")
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Telemetry loop error: {str(e)}")
                time.sleep(self.update_interval)
