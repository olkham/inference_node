import logging
import platform
import subprocess
from typing import Dict, List, Any, Optional

# Try to import additional libraries for hardware detection
try:
    import cpuinfo
    HAS_CPUINFO = True
except ImportError:
    HAS_CPUINFO = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class HardwareDetector():
    """Generic hardware detection for inference engines"""

    def __init__(self):
        """Initialize and detect all available hardware once"""
        self.hardware_info = self._detect_all_hardware()

    def __str__(self) -> str:
        return str(self.hardware_info)
    
    @property
    def available_devices(self) -> List[str]:
        """Get list of available devices"""
        return self.hardware_info.get('available_devices', [])
    
    def has_nvidia_gpu(self) -> bool:
        """Check if NVIDIA GPU is available"""
        return self.hardware_info['nvidia']['gpu']
    
    def has_intel_gpu(self) -> bool:
        """Check if Intel GPU is available"""
        return self.hardware_info['intel']['gpu']
    
    def has_intel_cpu(self) -> bool:
        """Check if Intel CPU is available"""
        return self.hardware_info['intel']['cpu']
    
    def has_intel_npu(self) -> bool:
        """Check if Intel NPU is available"""
        return self.hardware_info['intel']['npu']
    
    def has_amd_gpu(self) -> bool:
        """Check if AMD GPU is available"""
        return self.hardware_info['amd']['gpu']
    
    def has_amd_cpu(self) -> bool:
        """Check if AMD CPU is available"""
        return self.hardware_info['amd']['cpu']
    
    def has_apple_silicon(self) -> bool:
        """Check if Apple Silicon is available"""
        return self.hardware_info['apple']['cpu']
    
    def has_apple_neural_engine(self) -> bool:
        """Check if Apple Neural Engine is available"""
        return self.hardware_info['apple']['neural_engine']
    
    def has_raspberry_pi_cpu(self) -> bool:
        """Check if Raspberry Pi CPU is available"""
        return self.hardware_info['raspberry_pi']['cpu']
    
    def has_raspberry_pi_gpu(self) -> bool:
        """Check if Raspberry Pi GPU (VideoCore) is available"""
        return self.hardware_info['raspberry_pi']['gpu']
    
    def get_nvidia_gpu_count(self) -> int:
        """Get number of NVIDIA GPUs"""
        return self.hardware_info['nvidia']['gpu_count']
    
    def get_nvidia_gpu_devices(self) -> List[str]:
        """Get list of NVIDIA GPU device IDs (e.g., ['0', '1'])"""
        return self.hardware_info.get('nvidia', {}).get('gpu_devices', [])
    
    def get_nvidia_gpu_details(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about NVIDIA GPUs.
        
        Returns:
            Dict mapping device IDs to their details:
            {
                '0': {
                    'name': 'NVIDIA GeForce RTX 3090',
                    'uuid': 'GPU-3a913b3b-4002-8c29-ae33-483377f4c0b1',
                    'device_id': '0'
                },
                '1': {
                    'name': 'NVIDIA GeForce RTX 3090',
                    'uuid': 'GPU-1dbc9e18-593b-ee76-2f4f-5ad9612904a1',
                    'device_id': '1'
                }
            }
        """
        return self.hardware_info.get('nvidia', {}).get('gpu_details', {})
    
    def get_nvidia_gpu_friendly_name(self, device_id: str) -> str:
        """
        Get a user-friendly name for an NVIDIA GPU device.
        
        Args:
            device_id: CUDA device ID (e.g., '0', '1')
            
        Returns:
            Friendly name like "NVIDIA GeForce RTX 3090"
        """
        gpu_details = self.get_nvidia_gpu_details()
        
        if device_id in gpu_details:
            details = gpu_details[device_id]
            name = details['name']
            
            # Name is already in a good format from nvidia-smi
            return name
        
        # Fallback for unknown devices
        return f"NVIDIA GPU {device_id}"
    
    def get_nvidia_gpu_description(self, device_id: str) -> str:
        """
        Get a description for an NVIDIA GPU device.
        
        Args:
            device_id: CUDA device ID (e.g., '0', '1')
            
        Returns:
            Description with GPU info
        """
        gpu_details = self.get_nvidia_gpu_details()
        
        if device_id in gpu_details:
            details = gpu_details[device_id]
            name = details['name']
            
            # Extract series info (RTX, GTX, Tesla, etc.)
            if 'RTX' in name:
                return "NVIDIA RTX Series GPU"
            elif 'GTX' in name:
                return "NVIDIA GTX Series GPU"
            elif 'Tesla' in name:
                return "NVIDIA Tesla Data Center GPU"
            elif 'Quadro' in name:
                return "NVIDIA Quadro Professional GPU"
            elif 'A100' in name or 'A40' in name or 'A30' in name or 'A10' in name:
                return "NVIDIA Ampere Data Center GPU"
            elif 'H100' in name or 'H200' in name:
                return "NVIDIA Hopper Data Center GPU"
            else:
                return "NVIDIA GPU"
        
        # Fallback
        return "NVIDIA Graphics Processor"
    
    def get_intel_gpu_count(self) -> int:
        """Get number of Intel GPUs detected by OpenVINO"""
        gpu_devices = self.hardware_info.get('intel', {}).get('gpu_devices', [])
        return len(gpu_devices)
    
    def get_intel_gpu_devices(self) -> List[str]:
        """Get list of Intel GPU device IDs (e.g., ['GPU.0', 'GPU.1'])"""
        return self.hardware_info.get('intel', {}).get('gpu_devices', [])
    
    def get_intel_gpu_details(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about Intel GPUs.
        
        Returns:
            Dict mapping device IDs to their details:
            {
                'GPU.0': {
                    'name': 'Intel(R) UHD Graphics 770',
                    'type': 'iGPU',
                    'is_igpu': True,
                    'device_id': 'GPU.0'
                },
                'GPU.1': {
                    'name': 'Intel(R) Arc(TM) B580 Graphics',
                    'type': 'dGPU',
                    'is_igpu': False,
                    'device_id': 'GPU.1'
                }
            }
        """
        return self.hardware_info.get('intel', {}).get('gpu_details', {})
    
    def get_intel_gpu_friendly_name(self, device_id: str) -> str:
        """
        Get a user-friendly name for an Intel GPU device.
        
        Args:
            device_id: OpenVINO device ID (e.g., 'GPU.0', 'GPU.1')
            
        Returns:
            Friendly name like "Intel UHD Graphics (iGPU)" or "Intel Arc B580 (dGPU)"
        """
        gpu_details = self.get_intel_gpu_details()
        
        if device_id in gpu_details:
            details = gpu_details[device_id]
            name = details['name']
            gpu_type = details['type']
            
            # Simplify the name by removing common prefixes
            name = name.replace('Intel(R) ', '').replace('(R)', '').replace('(TM)', '')
            name = name.replace('Graphics', '').strip()
            
            # Remove any existing (iGPU) or (dGPU) markers to avoid duplication
            name = name.replace('(iGPU)', '').replace('(dGPU)', '').strip()
            
            return f"Intel {name} ({gpu_type})"
        
        # Fallback for unknown devices
        return f"Intel GPU {device_id}"
    
    def get_intel_gpu_description(self, device_id: str) -> str:
        """
        Get a description for an Intel GPU device.
        
        Args:
            device_id: OpenVINO device ID (e.g., 'GPU.0', 'GPU.1')
            
        Returns:
            Description like "Integrated Graphics" or "Discrete Graphics Card"
        """
        gpu_details = self.get_intel_gpu_details()
        
        if device_id in gpu_details:
            details = gpu_details[device_id]
            is_igpu = details['is_igpu']
            
            if is_igpu:
                return "On-chip integrated graphics"
            else:
                return "Dedicated graphics card"
        
        # Fallback
        return "Intel GPU Processing"
    
    def get_intel_npu_devices(self) -> List[str]:
        """Get list of Intel NPU/VPU device IDs"""
        return self.hardware_info.get('intel', {}).get('npu_devices', [])

    def _run_command(self, command: str, timeout: int = 10) -> Optional[str]:
        """
        Helper method to run a subprocess command safely.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            
        Returns:
            Command output as string, or None if command failed
        """
        try:
            return subprocess.check_output(command, shell=True, text=True, 
                                          timeout=timeout, stderr=subprocess.DEVNULL)
        except Exception:
            return None

    def _parse_nvidia_smi_line(self, line: str) -> Optional[Dict[str, str]]:
        """
        Parse a line from nvidia-smi -L output.
        
        Args:
            line: Line like "GPU 0: NVIDIA GeForce RTX 3090 (UUID: GPU-...)"
            
        Returns:
            Dict with device_id, name, and uuid, or None if parsing fails
        """
        if not line.startswith('GPU'):
            return None
            
        parts = line.split(':', 2)
        if len(parts) < 2:
            return None
            
        device_id = parts[0].replace('GPU', '').strip()
        rest = ':'.join(parts[1:]).strip()
        
        if '(UUID:' in rest:
            name = rest.split('(UUID:')[0].strip()
            uuid_part = rest.split('(UUID:')[1].strip()
            uuid = uuid_part.rstrip(')')
        else:
            name = rest
            uuid = ''
        
        return {
            'device_id': device_id,
            'name': name,
            'uuid': uuid
        }

    def _detect_all_hardware(self) -> Dict[str, Any]:
        """
        Detect all available hardware for inference.
        
        Returns:
            Dict containing hardware information organized by vendor and type,
            plus a list of available devices under 'available_devices'.
        """
        hardware_info = {
            'intel': self._detect_intel_hardware(),
            'nvidia': self._detect_nvidia_hardware(),
            'amd': self._detect_amd_hardware(),
            'apple': self._detect_apple_hardware(),
            'raspberry_pi': self._detect_raspberry_pi_hardware(),
            # 'generic': self._detect_generic_hardware(),
        }
        
        # Create a flattened list of available devices
        available_devices: List[str] = []
        for vendor, devices in hardware_info.items():
            if isinstance(devices, dict):
                for device_type, available in devices.items():
                    # Skip metadata and device list fields
                    if device_type in ['gpu_count', 'gpu_devices', 'gpu_details', 'npu_devices']:
                        continue
                        
                    if available and device_type not in ['gpu_count']:  # Skip metadata fields
                        # Special handling for NVIDIA GPU - check if CUDA is actually available
                        if vendor == 'nvidia' and device_type == 'gpu':
                            try:
                                import torch
                                if torch.cuda.is_available():
                                    # Don't add generic nvidia:gpu if we have specific GPU devices
                                    if not hardware_info.get('nvidia', {}).get('gpu_devices'):
                                        available_devices.append(f"{vendor}:{device_type}")
                                # Skip adding NVIDIA GPU if CUDA is not available
                            except ImportError:
                                # Skip adding NVIDIA GPU if PyTorch is not available
                                pass
                        elif vendor == 'generic':
                            available_devices.append(device_type.upper())
                        # Skip generic intel:gpu if we have specific GPU devices
                        elif vendor == 'intel' and device_type == 'gpu':
                            # Only add generic intel:gpu if no specific GPU devices are detected
                            if not hardware_info.get('intel', {}).get('gpu_devices'):
                                available_devices.append(f"{vendor}:{device_type}")
                        # Skip generic intel:npu if we have specific NPU devices
                        elif vendor == 'intel' and device_type == 'npu':
                            # Only add generic intel:npu if no specific NPU devices are detected
                            if not hardware_info.get('intel', {}).get('npu_devices'):
                                available_devices.append(f"{vendor}:{device_type}")
                        else:
                            available_devices.append(f"{vendor}:{device_type}")
        
        # Add individual NVIDIA GPU devices with their IDs (e.g., cuda:0, cuda:1)
        if 'nvidia' in hardware_info and 'gpu_devices' in hardware_info['nvidia']:
            for gpu_device in hardware_info['nvidia']['gpu_devices']:
                # Add each GPU device as cuda:0, cuda:1, etc.
                available_devices.append(f"cuda:{gpu_device}")
        
        # Add individual Intel GPU devices with their IDs (e.g., GPU.0, GPU.1)
        if 'intel' in hardware_info and 'gpu_devices' in hardware_info['intel']:
            for gpu_device in hardware_info['intel']['gpu_devices']:
                # Add each GPU device with its specific ID
                available_devices.append(f"intel:{gpu_device.lower()}")
        
        # Add individual Intel NPU devices with their IDs if available
        if 'intel' in hardware_info and 'npu_devices' in hardware_info['intel']:
            for npu_device in hardware_info['intel']['npu_devices']:
                # Add each NPU device with its specific ID
                available_devices.append(f"intel:{npu_device.lower()}")
        
        # Always ensure CPU is available as fallback, but only if no vendor-specific CPU is detected
        has_vendor_cpu = any('cpu' in device.lower() for device in available_devices)
        if not has_vendor_cpu:
            available_devices.append('CPU')
        
        # Add available_devices as a separate field
        result: Dict[str, Any] = dict(hardware_info)
        result['available_devices'] = available_devices
        return result
    
    def _is_integrated_gpu(self, gpu_name: str) -> bool:
        """
        Determine if a GPU is integrated (iGPU) or discrete (dGPU) based on its name.
        
        Intel integrated GPUs typically have names like:
        - Intel(R) UHD Graphics
        - Intel(R) Iris(R) Xe Graphics
        - Intel(R) HD Graphics
        - Intel(R) Arc(TM) Graphics (with model numbers like 130V, 140V - laptop integrated)
        
        Intel discrete GPUs have names like:
        - Intel(R) Arc(TM) A-Series Graphics (A310, A380, A580, A750, A770)
        - Intel(R) Arc(TM) Pro Graphics (Pro A-Series)
        - Intel(R) Data Center GPU
        """
        gpu_name_lower = gpu_name.lower()
        
        # Check if name explicitly indicates (iGPU) or (dGPU) first
        if '(igpu)' in gpu_name_lower:
            return True
        if '(dgpu)' in gpu_name_lower:
            return False
        
        # Integrated GPU indicators (checked first for higher priority)
        integrated_indicators = [
            'uhd graphics',      # Modern integrated
            'iris xe',           # Modern integrated
            'iris plus',         # Older integrated
            'hd graphics',       # Older integrated
            'iris graphics',     # Older integrated
            'graphics media accelerator',  # Very old
            # Arc mobile integrated (laptop chips)
            'arc(tm) 1',        # Arc 130V, 140V series (mobile integrated)
        ]
        
        # Discrete GPU indicators
        discrete_indicators = [
            'arc(tm) a',        # Intel Arc A-Series (A310, A380, A580, A750, A770 - desktop discrete)
            'arc(tm) pro',      # Arc Pro series (workstation discrete)
            'data center',      # Intel Data Center GPU Flex/Max
            'ponte vecchio',    # Intel Xe HPC
            'alchemist',        # Arc codename (desktop)
            'battlemage',       # Arc next-gen codename
            'druid'             # Arc future codename
        ]
        
        # Check for integrated GPU indicators first (higher priority)
        for indicator in integrated_indicators:
            if indicator in gpu_name_lower:
                return True  # It's an iGPU
        
        # Then check for discrete GPU indicators
        for indicator in discrete_indicators:
            if indicator in gpu_name_lower:
                return False  # It's a dGPU
        
        # Default to integrated if we can't determine
        # (safer assumption for unknown Intel GPUs - most Intel GPUs are integrated)
        return True
    
    def _detect_intel_hardware(self) -> Dict[str, Any]:
        """Detect available Intel hardware components using OpenVINO's built-in device detection"""
        intel_devices: Dict[str, Any] = {
            'cpu': False,
            'gpu': False,
            'npu': False,
            'gpu_devices': [],  # List of GPU device IDs (e.g., ['GPU.0', 'GPU.1'])
            'gpu_details': {},  # Detailed info for each GPU: {device_id: {name, type, is_igpu}}
            'npu_devices': []   # List of NPU/VPU device IDs
        }

        # Prefer OpenVINO's device enumeration when available - this is the most
        # reliable way to discover Intel devices supported by OpenVINO.
        try:
            from openvino.runtime import Core

            try:
                core = Core()
                available = core.available_devices
                # available is typically a list like ['CPU', 'GPU', 'GPU.0', 'GPU.1', 'MYRIAD', 'NPU']
                
                for dev in available:
                    ld = dev.lower()
                    
                    # Detect CPU
                    if ld == 'cpu':
                        # Verify this is actually an Intel CPU before claiming support
                        if self._is_intel_cpu():
                            intel_devices['cpu'] = True
                    
                    # Detect GPU devices - OpenVINO reports them as 'GPU', 'GPU.0', 'GPU.1', etc.
                    if 'gpu' in ld:
                        intel_devices['gpu'] = True
                        # Store the exact device ID for multi-GPU systems
                        if dev not in intel_devices['gpu_devices']:
                            intel_devices['gpu_devices'].append(dev)
                            
                            # Get detailed GPU information from OpenVINO
                            try:
                                full_name = core.get_property(dev, "FULL_DEVICE_NAME")
                                
                                # Determine if it's integrated (iGPU) or discrete (dGPU)
                                is_igpu = self._is_integrated_gpu(full_name)
                                gpu_type = "iGPU" if is_igpu else "dGPU"
                                
                                intel_devices['gpu_details'][dev] = {
                                    'name': full_name,
                                    'type': gpu_type,
                                    'is_igpu': is_igpu,
                                    'device_id': dev
                                }
                            except Exception as e:
                                # Fallback if we can't get detailed properties
                                logging.getLogger(__name__).debug(f"Could not get GPU details for {dev}: {e}")
                                intel_devices['gpu_details'][dev] = {
                                    'name': f"Intel GPU {dev}",
                                    'type': "GPU",
                                    'is_igpu': False,
                                    'device_id': dev
                                }
                    
                    # Map common OpenVINO device names to 'npu' (NPU/VPU/GNA family)
                    # NPU, GNA (Gaussian & Neural Accelerator), MYRIAD, VPU, VPUX, HDDL
                    if any(k in ld for k in ('gna', 'myriad', 'vpu', 'vpux', 'hddl', 'npu')):
                        intel_devices['npu'] = True
                        if dev not in intel_devices['npu_devices']:
                            intel_devices['npu_devices'].append(dev)
                
                # If we successfully got OpenVINO device info, return it
                if intel_devices['cpu'] or intel_devices['gpu'] or intel_devices['npu']:
                    return intel_devices
                    
            except Exception as e:
                # If OpenVINO import succeeded but querying devices failed,
                # fall through to the legacy detection logic below.
                logging.getLogger(__name__).debug(f"OpenVINO device query failed: {e}")
                pass
        except ImportError:
            # OpenVINO not installed - use legacy detection
            logging.getLogger(__name__).debug("OpenVINO not available, using legacy Intel detection")
            pass

        # Legacy detection (kept for environments without OpenVINO)
        # Try using cpuinfo library first (most reliable)
        if HAS_CPUINFO:
            try:
                cpu_info_dict = cpuinfo.get_cpu_info()
                brand = cpu_info_dict.get('brand_raw', '') or cpu_info_dict.get('brand', '')
                if 'Intel' in brand:
                    intel_devices['cpu'] = True
            except Exception:
                pass

        # Fallback to system-specific methods if cpuinfo not available or failed
        if not intel_devices['cpu']:
            try:
                # Check CPU vendor using platform module first
                processor_info = platform.processor()
                if 'Intel' in processor_info:
                    intel_devices['cpu'] = True
                else:
                    # Platform-specific detection
                    if platform.system() == "Windows":
                        try:
                            # Try PowerShell method first
                            cpu_info = subprocess.check_output(
                                'powershell "Get-WmiObject -Class Win32_Processor | Select-Object Name"',
                                shell=True, text=True, timeout=10
                            )
                            if "Intel" in cpu_info:
                                intel_devices['cpu'] = True
                        except Exception:
                            try:
                                # Fallback to environment variables
                                cpu_info = subprocess.check_output("echo %PROCESSOR_IDENTIFIER%", shell=True, text=True, timeout=5)
                                if "Intel" in cpu_info:
                                    intel_devices['cpu'] = True
                            except Exception:
                                pass
                    else:
                        # Linux/Mac - check /proc/cpuinfo or similar
                        try:
                            with open('/proc/cpuinfo', 'r') as f:
                                cpu_info = f.read()
                                if "Intel" in cpu_info:
                                    intel_devices['cpu'] = True
                        except Exception:
                            # Fallback for Mac or other systems
                            try:
                                cpu_info = subprocess.check_output("sysctl -n machdep.cpu.brand_string", shell=True, text=True, timeout=5)
                                if "Intel" in cpu_info:
                                    intel_devices['cpu'] = True
                            except Exception:
                                pass
            except Exception:
                pass

        # Check for Intel GPU (basic detection)
        try:
            if platform.system() == "Windows":
                try:
                    # Try PowerShell method first
                    gpu_info = subprocess.check_output(
                        'powershell "Get-WmiObject -Class Win32_VideoController | Select-Object Name"',
                        shell=True, text=True, timeout=10
                    )
                    if "Intel" in gpu_info:
                        intel_devices['gpu'] = True
                except Exception:
                    pass
            else:
                # Linux - check lspci for Intel graphics
                try:
                    gpu_info = subprocess.check_output("lspci | grep -i vga", shell=True, text=True, timeout=5)
                    if "Intel" in gpu_info:
                        intel_devices['gpu'] = True
                except Exception:
                    pass
        except Exception:
            pass

        # NPU detection - assume available for newer Intel generations
        try:
            if intel_devices['cpu']:  # Only check for NPU if Intel CPU is present
                if HAS_CPUINFO:
                    try:
                        cpu_info_dict = cpuinfo.get_cpu_info()
                        brand = cpu_info_dict.get('brand_raw', '') or cpu_info_dict.get('brand', '')
                        # Look for generation indicators in brand string or Intel Core Ultra processors
                        if any(gen in brand for gen in ['12th', '13th', '14th', '15th', 'i3-12', 'i5-12', 'i7-12', 'i9-12', 'i3-13', 'i5-13', 'i7-13', 'i9-13']) or 'Intel(R) Core(TM) Ultra' in brand:
                            intel_devices['npu'] = True
                    except Exception:
                        pass
                else:
                    # Fallback detection for newer Intel generations
                    if platform.system() == "Windows":
                        try:
                            # Try PowerShell first
                            cpu_info = subprocess.check_output(
                                'powershell "Get-WmiObject -Class Win32_Processor | Select-Object Name"',
                                shell=True, text=True, timeout=10
                            )
                            # Look for generation indicators or Intel Core Ultra processors
                            if any(gen in cpu_info for gen in ['12th', '13th', '14th', '15th', 'i3-12', 'i5-12', 'i7-12', 'i9-12', 'i3-13', 'i5-13', 'i7-13', 'i9-13']) or 'Intel(R) Core(TM) Ultra' in cpu_info:
                                intel_devices['npu'] = True
                        except Exception:
                            pass
        except Exception:
            pass

        return intel_devices
    
    def _detect_nvidia_hardware(self) -> Dict[str, Any]:
        """Detect available NVIDIA hardware components"""
        nvidia_devices: Dict[str, Any] = {
            'gpu': False,
            'gpu_count': 0,
            'gpu_devices': [],  # List of GPU device IDs (e.g., ['0', '1'])
            'gpu_details': {}   # Detailed info for each GPU: {device_id: {name, uuid}}
        }
        
        # Helper to populate GPU details from nvidia-smi or use count-based fallback
        def populate_gpu_details(nvidia_count: int):
            nvidia_smi_output = self._run_command("nvidia-smi -L")
            if nvidia_smi_output:
                for line in nvidia_smi_output.strip().split('\n'):
                    parsed = self._parse_nvidia_smi_line(line)
                    if parsed:
                        device_id = parsed['device_id']
                        nvidia_devices['gpu_devices'].append(device_id)
                        nvidia_devices['gpu_details'][device_id] = {
                            'name': parsed['name'],
                            'uuid': parsed['uuid'],
                            'device_id': device_id
                        }
            else:
                # Fallback: create basic entries based on count
                for i in range(nvidia_count):
                    device_id = str(i)
                    nvidia_devices['gpu_devices'].append(device_id)
                    nvidia_devices['gpu_details'][device_id] = {
                        'name': 'NVIDIA GPU',
                        'uuid': '',
                        'device_id': device_id
                    }
        
        if platform.system() == "Windows":
            # Try PowerShell WMI method first
            gpu_info = self._run_command('powershell "Get-WmiObject -Class Win32_VideoController | Select-Object Name"')
            if gpu_info:
                nvidia_count = gpu_info.count("NVIDIA")
                if nvidia_count > 0:
                    nvidia_devices['gpu'] = True
                    nvidia_devices['gpu_count'] = nvidia_count
                    populate_gpu_details(nvidia_count)
                    return nvidia_devices
            
            # Fallback to alternative PowerShell command
            gpu_info = self._run_command('powershell "Get-CimInstance -ClassName Win32_VideoController | Select-Object -ExpandProperty Name"')
            if gpu_info:
                nvidia_count = gpu_info.count("NVIDIA")
                if nvidia_count > 0:
                    nvidia_devices['gpu'] = True
                    nvidia_devices['gpu_count'] = nvidia_count
                    populate_gpu_details(nvidia_count)
                    return nvidia_devices
        else:
            # Linux - try nvidia-smi first
            nvidia_smi_output = self._run_command("nvidia-smi -L")
            if nvidia_smi_output:
                gpu_lines = [line for line in nvidia_smi_output.strip().split('\n') if line.startswith('GPU')]
                gpu_count = len(gpu_lines)
                if gpu_count > 0:
                    nvidia_devices['gpu'] = True
                    nvidia_devices['gpu_count'] = gpu_count
                    
                    for line in gpu_lines:
                        parsed = self._parse_nvidia_smi_line(line)
                        if parsed:
                            device_id = parsed['device_id']
                            nvidia_devices['gpu_devices'].append(device_id)
                            nvidia_devices['gpu_details'][device_id] = {
                                'name': parsed['name'],
                                'uuid': parsed['uuid'],
                                'device_id': device_id
                            }
                    return nvidia_devices
            
            # Fallback to lspci
            gpu_info = self._run_command("lspci | grep -i nvidia")
            if gpu_info and "NVIDIA" in gpu_info:
                nvidia_devices['gpu'] = True
                gpu_count = len([line for line in gpu_info.strip().split('\n') if line])
                nvidia_devices['gpu_count'] = gpu_count
                
                # Create basic device entries without detailed info
                for i in range(gpu_count):
                    device_id = str(i)
                    nvidia_devices['gpu_devices'].append(device_id)
                    nvidia_devices['gpu_details'][device_id] = {
                        'name': 'NVIDIA GPU',
                        'uuid': '',
                        'device_id': device_id
                    }
                return nvidia_devices
        
        return nvidia_devices
    
    def _detect_amd_hardware(self) -> Dict[str, bool]:
        """Detect available AMD hardware components"""
        amd_devices = {
            'cpu': False,
            'gpu': False
        }
        
        try:
            # Check CPU vendor
            if platform.system() == "Windows":
                try:
                    # Try PowerShell method first
                    cpu_info = subprocess.check_output(
                        'powershell "Get-WmiObject -Class Win32_Processor | Select-Object Name"', 
                        shell=True, text=True
                    )
                    if "AMD" in cpu_info:
                        amd_devices['cpu'] = True
                    
                    # Check for AMD GPU
                    gpu_info = subprocess.check_output(
                        'powershell "Get-WmiObject -Class Win32_VideoController | Select-Object Name"', 
                        shell=True, text=True
                    )
                    if "AMD" in gpu_info or "Radeon" in gpu_info:
                        amd_devices['gpu'] = True
                except Exception:
                    try:
                        # Fallback to alternative PowerShell commands
                        cpu_info = subprocess.check_output(
                            'powershell "Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty Name"', 
                            shell=True, text=True
                        )
                        if "AMD" in cpu_info:
                            amd_devices['cpu'] = True
                        
                        gpu_info = subprocess.check_output(
                            'powershell "Get-CimInstance -ClassName Win32_VideoController | Select-Object -ExpandProperty Name"', 
                            shell=True, text=True
                        )
                        if "AMD" in gpu_info or "Radeon" in gpu_info:
                            amd_devices['gpu'] = True
                    except Exception:
                        pass
            else:
                # Linux/Mac
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        cpu_info = f.read()
                        if "AMD" in cpu_info:
                            amd_devices['cpu'] = True
                except Exception:
                    pass
                
                # Check for AMD GPU
                try:
                    gpu_info = subprocess.check_output("lspci | grep -i amd", shell=True, text=True)
                    if "AMD" in gpu_info:
                        amd_devices['gpu'] = True
                except Exception:
                    pass
        except Exception:
            pass
        
        return amd_devices
    
    def _detect_apple_hardware(self) -> Dict[str, bool]:
        """Detect available Apple hardware components (M1/M2/M3 chips)"""
        apple_devices = {
            'neural_engine': False,
            'gpu': False,
            'cpu': False
        }
        
        try:
            if platform.system() == "Darwin":  # macOS
                # Check for Apple Silicon
                cpu_info = subprocess.check_output("sysctl -n machdep.cpu.brand_string", shell=True, text=True)
                if "Apple" in cpu_info:
                    apple_devices['cpu'] = True
                    # Apple Silicon chips have integrated Neural Engine and GPU
                    if any(chip in cpu_info for chip in ['M1', 'M2', 'M3']):
                        apple_devices['neural_engine'] = True
                        apple_devices['gpu'] = True
        except Exception:
            pass
        
        return apple_devices
    
    def _is_intel_cpu(self) -> bool:
        """Check if the CPU is actually an Intel CPU"""
        # Try using cpuinfo library first (most reliable)
        if HAS_CPUINFO:
            try:
                cpu_info_dict = cpuinfo.get_cpu_info()
                brand = cpu_info_dict.get('brand_raw', '') or cpu_info_dict.get('brand', '')
                if 'Intel' in brand:
                    return True
            except Exception:
                pass

        # Fallback to system-specific methods
        try:
            # Check CPU vendor using platform module first
            processor_info = platform.processor()
            if 'Intel' in processor_info:
                return True
        except Exception:
            pass

        # Platform-specific detection
        try:
            if platform.system() == "Windows":
                try:
                    # Try PowerShell method first
                    cpu_info = subprocess.check_output(
                        'powershell "Get-WmiObject -Class Win32_Processor | Select-Object Name"',
                        shell=True, text=True, timeout=10
                    )
                    if "Intel" in cpu_info:
                        return True
                except Exception:
                    try:
                        # Fallback to environment variables
                        cpu_info = subprocess.check_output("echo %PROCESSOR_IDENTIFIER%", shell=True, text=True, timeout=5)
                        if "Intel" in cpu_info:
                            return True
                    except Exception:
                        pass
            else:
                # Linux/Mac - check /proc/cpuinfo or similar
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        cpu_info = f.read()
                        if "Intel" in cpu_info:
                            return True
                except Exception:
                    # Fallback for Mac or other systems
                    try:
                        cpu_info = subprocess.check_output("sysctl -n machdep.cpu.brand_string", shell=True, text=True, timeout=5)
                        if "Intel" in cpu_info:
                            return True
                    except Exception:
                        pass
        except Exception:
            pass

        return False
    
    def _detect_raspberry_pi_hardware(self) -> Dict[str, bool]:
        """Detect if running on Raspberry Pi hardware"""
        raspberry_pi_devices = {
            'cpu': False,
            'gpu': False  # Raspberry Pi has VideoCore GPU
        }
        
        try:
            # Check /proc/cpuinfo for Raspberry Pi indicators
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                
            # Check for Broadcom hardware (BCM) or Raspberry Pi model
            if ('hardware' in cpuinfo and 'bcm' in cpuinfo) or \
               ('model' in cpuinfo and 'raspberry pi' in cpuinfo):
                raspberry_pi_devices['cpu'] = True
                # Raspberry Pi has VideoCore GPU
                raspberry_pi_devices['gpu'] = True
                
        except (FileNotFoundError, PermissionError, OSError):
            # /proc/cpuinfo not available or not readable
            pass
        
        return raspberry_pi_devices
    
    def get_optimal_device_for_hardware(self) -> str:
        """
        Get the optimal device string based on detected hardware.
        
        Returns:
            String representing the best available device
        """
        hardware = self.hardware_info
        
        # Priority order: NVIDIA GPU (with CUDA) > Intel GPU > Apple Neural Engine > Intel CPU > Generic CPU
        if hardware['nvidia']['gpu']:
            # Check if CUDA is actually available
            try:
                import torch
                if torch.cuda.is_available():
                    return 'cuda'  # or 'nvidia:gpu'
                else:
                    print("WARNING: NVIDIA GPU detected but CUDA not available. Skipping CUDA device.")
            except ImportError:
                print("WARNING: NVIDIA GPU detected but PyTorch not available to check CUDA. Skipping CUDA device.")
        
        if hardware['intel']['gpu']:
            return 'intel:gpu'
        elif hardware['apple']['neural_engine']:
            return 'mps'  # Metal Performance Shaders for Apple
        elif hardware['intel']['cpu']:
            return 'intel:cpu'
        else:
            return 'cpu'
    
    def optimize_device_string(self, device: str, hardware_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Optimize device string based on available hardware.
        
        Args:
            device: Original device string
            hardware_info: Pre-detected hardware info (optional, uses self.hardware_info if None)
            
        Returns:
            Optimized device string
        """
        if hardware_info is None:
            hardware_info = self.hardware_info
        
        if device is None:
            device = "CPU"
        
        device = device.upper()
        
        # Handle device indices (e.g., GPU.0, GPU.1, CPU.0)
        device_base = device
        device_index = ""
        if "." in device:
            device_parts = device.split(".", 1)
            device_base = device_parts[0]
            device_index = f".{device_parts[1]}"
        
        # Map device strings to vendor-specific formats
        if device_base == 'CPU':
            if hardware_info['intel']['cpu']:
                return f"intel:cpu{device_index}".lower()
            elif hardware_info['amd']['cpu']:
                return f"amd:cpu{device_index}".lower()
            elif hardware_info['apple']['cpu']:
                return f"mps{device_index}".lower()
            else:
                return f"cpu{device_index}".lower()
        
        elif device_base == 'GPU':
            if hardware_info['nvidia']['gpu']:
                return f"cuda{device_index}".lower()
            elif hardware_info['intel']['gpu']:
                return f"intel:gpu{device_index}".lower()
            elif hardware_info['amd']['gpu']:
                return f"amd:gpu{device_index}".lower()
            elif hardware_info['apple']['gpu']:
                return f"mps{device_index}".lower()
            else:
                return f"gpu{device_index}".lower()
        
        elif device_base == 'NPU':
            if hardware_info['intel']['npu']:
                return f"intel:npu{device_index}".lower()
            else:
                return f"npu{device_index}".lower()
        
        # Return as-is if already vendor-specific or unrecognized
        return device.lower()

    def format_for(self, engine, device: str) -> str:
        """
        Format the device string for a specific inference engine.
        """
        optimized_device = self.optimize_device_string(device)

        # if engine type is ultralytics intel optimisations are preceeded with intel e.g. intel:cpu, or intel:gpu
        if engine == "ultralytics":
            return optimized_device

        # if engine type is geti or openvino, the strings are 'cpu, gpu, npu, auto, or gpu.index e.g. gpu.0, gpu.1
        if engine in ["geti", "openvino"]:
            if optimized_device.startswith("intel:"):
                return optimized_device.split(":")[-1]

        return optimized_device

    def get_gpu_details(self) -> List[Dict[str, Any]]:
        """Get detailed GPU information"""
        gpu_details = []
        try:
            hw_info = self.hardware_info
            
            # NVIDIA GPUs
            nvidia_gpu = hw_info.get('nvidia', {}).get('gpu')
            if nvidia_gpu:
                # Handle both boolean and list formats
                if isinstance(nvidia_gpu, list):
                    for gpu in nvidia_gpu:
                        gpu_details.append({
                            'name': gpu.get('name', 'NVIDIA GPU'),
                            'memory_total': gpu.get('memory_total', 0),
                            'driver_version': gpu.get('driver_version', 'Unknown'),
                            'type': 'NVIDIA'
                        })
                elif nvidia_gpu is True:
                    # Just a boolean flag, add generic GPU info
                    gpu_details.append({
                        'name': 'NVIDIA GPU',
                        'memory_total': 0,
                        'driver_version': 'Unknown',
                        'type': 'NVIDIA'
                    })
            
            # Intel GPUs
            intel_gpu = hw_info.get('intel', {}).get('gpu')
            if intel_gpu:
                if isinstance(intel_gpu, list):
                    for gpu in intel_gpu:
                        gpu_details.append({
                            'name': gpu.get('name', 'Intel GPU'),
                            'memory_total': gpu.get('memory_total', 0),
                            'driver_version': gpu.get('driver_version', 'Unknown'),
                            'type': 'Intel'
                        })
                elif intel_gpu is True:
                    gpu_details.append({
                        'name': 'Intel GPU',
                        'memory_total': 0,
                        'driver_version': 'Unknown',
                        'type': 'Intel'
                    })
            
            # AMD GPUs
            amd_gpu = hw_info.get('amd', {}).get('gpu')
            if amd_gpu:
                if isinstance(amd_gpu, list):
                    for gpu in amd_gpu:
                        gpu_details.append({
                            'name': gpu.get('name', 'AMD GPU'),
                            'memory_total': gpu.get('memory_total', 0),
                            'driver_version': gpu.get('driver_version', 'Unknown'),
                            'type': 'AMD'
                        })
                elif amd_gpu is True:
                    gpu_details.append({
                        'name': 'AMD GPU',
                        'memory_total': 0,
                        'driver_version': 'Unknown',
                        'type': 'AMD'
                    })
            
            # Apple GPUs
            apple_gpu = hw_info.get('apple', {}).get('gpu')
            if apple_gpu:
                if isinstance(apple_gpu, list):
                    for gpu in apple_gpu:
                        gpu_details.append({
                            'name': gpu.get('name', 'Apple GPU'),
                            'memory_total': gpu.get('memory_total', 0),
                            'driver_version': gpu.get('driver_version', 'Unknown'),
                            'type': 'Apple'
                        })
                elif apple_gpu is True:
                    gpu_details.append({
                        'name': 'Apple GPU',
                        'memory_total': 0,
                        'driver_version': 'Unknown',
                        'type': 'Apple'
                    })
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to get GPU details: {e}")
        
        return gpu_details

    def get_storage_details(self) -> List[Dict[str, Any]]:
        """Get detailed storage information"""
        storage_details = []
        try:
            import psutil
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    storage_details.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': (usage.used / usage.total) * 100
                    })
                except PermissionError:
                    # Skip partitions we can't access
                    continue
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to get storage details: {e}")
        
        return storage_details

if __name__ == "__main__":
    # Simple test of the hardware detection
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Testing HardwareDetector...")
    
    detector = HardwareDetector()
    logger.info(f"Detected hardware: {detector.hardware_info}")
    
    optimal_device = detector.get_optimal_device_for_hardware()
    logger.info(f"Optimal device: {optimal_device}")
    
    test_devices = ['CPU', 'GPU', 'GPU.0', 'intel:cpu', 'cuda']
    for device in test_devices:
        optimized = detector.optimize_device_string(device)
        logger.info(f"Device '{device}' optimized to: '{optimized}'")