#!/usr/bin/env python3
"""
Setup script for InferNode platform

This script helps install dependencies and set up the InferNode environment.
"""

import os
import sys
import subprocess
import platform

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\\n{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed:")
        print(f"  Command: {command}")
        print(f"  Error: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"✗ Python 3.10+ required, found {version.major}.{version.minor}")
        return False
    else:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} detected")
        return True

def install_core_dependencies():
    """Install core dependencies"""
    print("\\n=== Installing Core Dependencies ===")
    
    core_packages = [
        "flask>=2.0.0",
        "psutil>=5.8.0", 
        "paho-mqtt>=1.6.0",
        "requests>=2.25.0",
        "opencv-python>=4.5.0",
        "numpy>=1.21.0",
        "Pillow>=8.0.0"
    ]
    
    for package in core_packages:
        if not run_command(f"pip install {package}", f"Installing {package}"):
            return False
    
    return True

def install_optional_dependencies():
    """Install optional dependencies based on user choice"""
    print("\\n=== Optional Dependencies ===")
    
    optional_groups = {
        "AI/ML Frameworks (PyTorch, Ultralytics)": [
            "torch>=1.11.0",
            "torchvision>=0.12.0", 
            "ultralytics>=8.0.0"
        ],
        "GPU Monitoring (NVIDIA)": [
            "pynvml>=11.0.0"
        ],
        "Serial Communication": [
            "pyserial>=3.5"
        ],
        "Development Tools": [
            "pytest>=6.0.0",
            "black>=21.0.0",
            "flake8>=3.9.0"
        ]
    }
    
    for group_name, packages in optional_groups.items():
        response = input(f"Install {group_name}? (y/N): ").lower().strip()
        if response in ['y', 'yes']:
            for package in packages:
                run_command(f"pip install {package}", f"Installing {package}")

def create_directories():
    """Create necessary directories"""
    print("\\n=== Creating Directories ===")
    
    directories = [
        "models",
        "logs",
        "temp"
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✓ Created directory: {directory}")
        except Exception as e:
            print(f"✗ Failed to create directory {directory}: {e}")

def check_system_capabilities():
    """Check system capabilities"""
    print("\\n=== System Capabilities ===")
    
    print(f"Platform: {platform.platform()}")
    print(f"Processor: {platform.processor()}")
    print(f"Architecture: {platform.architecture()[0]}")
    
    try:
        import psutil
        print(f"CPU cores: {psutil.cpu_count()}")
        print(f"Memory: {round(psutil.virtual_memory().total / (1024**3), 2)} GB")
    except ImportError:
        print("psutil not available for detailed system info")
    
    # Check for GPU
    gpu_detected = False
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count > 0:
            print(f"✓ NVIDIA GPU detected: {device_count} device(s)")
            gpu_detected = True
    except:
        pass
    
    if not gpu_detected:
        print("No NVIDIA GPU detected (CPU-only mode)")

def create_example_config():
    """Create example configuration files"""
    print("\\n=== Creating Example Configuration ===")
    
    config_content = '''# InferNode Configuration Example
# Copy this file to config.py and customize as needed

# Node configuration
NODE_NAME = "MyInferNode"
NODE_PORT = 5000

# MQTT configuration for telemetry
MQTT_SERVER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "infernode"
MQTT_USERNAME = None
MQTT_PASSWORD = None

# Discovery configuration
DISCOVERY_PORT = 8888
ENABLE_DISCOVERY = True

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FILE = "logs/infernode.log"

# Default inference settings
DEFAULT_DEVICE = "cpu"  # or "cuda", "mps", etc.
MAX_BATCH_SIZE = 1
'''
    
    try:
        with open('config_example.py', 'w') as f:
            f.write(config_content)
        print("✓ Created config_example.py")
    except Exception as e:
        print(f"✗ Failed to create config example: {e}")

def main():
    """Main setup function"""
    print("InferNode Platform Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check if pip is available
    if not run_command("pip --version", "Checking pip availability"):
        print("Please install pip before running setup")
        sys.exit(1)
    
    # Install dependencies
    if not install_core_dependencies():
        print("\\n✗ Core dependency installation failed")
        response = input("Continue with optional dependencies? (y/N): ")
        if response.lower().strip() not in ['y', 'yes']:
            sys.exit(1)
    
    # Install optional dependencies
    install_optional_dependencies()
    
    # Create directories
    create_directories()
    
    # Check system capabilities
    check_system_capabilities()
    
    # Create example configuration
    create_example_config()
    
    print("\\n" + "=" * 50)
    print("✓ InferNode setup completed!")
    print("\\nNext steps:")
    print("1. Review and customize config_example.py")
    print("2. Run the example: python example.py")
    print("3. Start a node: python inference_node.py")
    print("4. Check the API at http://localhost:5000/api/info")
    print("\\nDocumentation: See README.md for detailed usage")

if __name__ == "__main__":
    main()
