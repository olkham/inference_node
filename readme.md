# InferNode
## A scalable inference platform that provides multi-node management and control for AI/ML inference workloads.

### It enables easy deployment and management of inference pipelines across distributed nodes with auto-discovery, telemetry, and flexible result publishing.

## 📺 Demo Video
https://github.com/user-attachments/assets/5ed323d7-e8cf-421a-be8f-781e3f51c9a0

## 🚀 Features - Scalable Inference Platform

### Core Capabilities
- **Multi-engine support**: Ultralytics YOLO, Geti, and custom engines
- **Auto-discovery**: Nodes automatically discover each other on the network
- **Real-time telemetry**: System monitoring and performance metrics via MQTT
- **Flexible result publishing**: MQTT, webhooks, serial, and custom destinations
- **RESTful API**: Complete HTTP API for remote management
- **Rate limiting**: Built-in rate limiting for all result destinations

### Supported Inference Engines
- **Ultralytics**: YOLO object detection models (YOLOv8, YOLOv11, etc.)
- **Geti**: Intel's computer vision platform
- **Pass-through**: For testing and development
- **Custom**: Extensible framework for custom implementations

### Result Destinations
- **MQTT**: Publish results to MQTT brokers
- **Webhook**: HTTP POST to custom endpoints
- **Serial**: Output to serial ports (RS-232, USB)
- **OPC UA**: Industrial automation protocol
- **ROS2**: Robot Operating System 2
- **ZeroMQ**: High-performance messaging
- **Folder**: Save to local/network filesystem
- **Roboflow**: Integration with Roboflow platform
- **Geti**: Geti platform integration
- **Custom**: Implement your own destinations

## 📋 Requirements

- Python 3.10+
- Compatible with Windows, Linux
- Optional: CUDA for GPU acceleration
- Optional: MQTT broker for telemetry and result publishing

> **Note:** Only tested on a limited set of configurations so far (Windows / Ubuntu) x (Intel / Nvidia) - AMD and more is on the #todo list

## 🛠️ Installation

### Quick Start
```bash
# Clone the repository
git clone https://github.com/olkham/inference_node.git
cd inference_node

# Run the setup script (Windows)
setup.bat

# Or on Linux/macOS
chmod +x setup.sh
./setup.sh
```

### Manual Installation
```bash
# Install core dependencies
pip install -r requirements.txt

# Optional: Install AI/ML frameworks (if not already in requirements.txt)
pip install torch torchvision ultralytics geti-sdk

# Optional: Install GPU monitoring (uses nvidia-ml-py, not deprecated pynvml)
pip install nvidia-ml-py>=12.0.0

# Optional: Install serial communication
pip install pyserial>=3.5
```

## 🏃‍♂️ Quick Start

### 1. Start an Inference Node
```python
from InferenceNode import InferenceNode

# Create and start a node
node = InferenceNode("MyNode", port=5555)
node.start(enable_discovery=True, enable_telemetry=True)
```

Or use the command line:
```bash
# Start full node with all services using Flask
python main.py

# Start full node with all services using waitress (production mode)
python main.py --production

# Start with custom settings
python main.py --port 8080 --name "ProductionNode" --no-telemetry
```

### 2. Using Inference Engines
```python
from InferenceEngine import InferenceEngine

# Create different engine types
ie_ultralytics = InferenceEngine('ultralytics')
ie_torch = InferenceEngine('torch')
ie_custom = InferenceEngine('custom')

# Upload and load a model
model_id = ie_ultralytics.upload('path/to/model.pt')
ie_ultralytics.load(model_id, device='cuda')

# Run inference
result = ie_ultralytics.infer('path/to/image.jpg')
```

### 3. Configure Result Publishing
```python
from ResultPublisher import ResultPublisher, ResultDestination

# Create result publisher
rp = ResultPublisher()

# Configure MQTT destination
rd_mqtt = ResultDestination('mqtt')
rd_mqtt.configure(
    server='localhost',
    topic='infernode/results',
    rate_limit=1.0  # 1 second between publishes
)
rp.add(rd_mqtt)

# Configure webhook destination
rd_webhook = ResultDestination('webhook')
rd_webhook.configure(
    url='http://myserver.com/webhook',
    rate_limit=0.5
)
rp.add(rd_webhook)

# Publish results
rp.publish({"inference_results": "data"})
```

## 🔧 API Reference

### Node Information
```bash
GET /api/info
```
Returns node capabilities and status.

### Engine Management
```bash
# Load an inference engine
POST /api/engine/load
{
  "engine_type": "ultralytics",
  "model_id": "model_123",
  "device": "cuda"
}

# Upload a model
POST /api/engine/upload
# Form data with file upload
```

### Inference
```bash
POST /api/inference
# Form data with image file or JSON with image_path
```

### Result Publisher Configuration
```bash
POST /api/publisher/configure
{
  "type": "mqtt",
  "config": {
    "server": "localhost",
    "topic": "results",
    "rate_limit": 1.0
  }
}
```

### Telemetry Control
```bash
# Start telemetry
POST /api/telemetry/start
{
  "mqtt": {
    "mqtt_server": "localhost",
    "mqtt_topic": "telemetry"
  }
}

# Stop telemetry
POST /api/telemetry/stop
```

## 📁 Project Structure

```
inference_node/
├── InferenceEngine/          # Inference engine implementations
│   ├── engines/
│   │   ├── base_engine.py        # Base class for all engines
│   │   ├── ultralytics_engine.py # Ultralytics YOLO support
│   │   ├── geti_engine.py        # Geti support
│   │   ├── pass_engine.py        # Pass-through engine
│   │   └── example_engine_template.py # Custom engine template
│   ├── inference_engine_factory.py
│   └── result_converters.py
├── InferenceNode/            # Main node implementation
│   ├── inference_node.py     # Core node class
│   ├── pipeline_manager.py   # Pipeline orchestration
│   ├── pipeline.py           # Pipeline definitions
│   ├── discovery_manager.py  # Network discovery
│   ├── telemetry.py          # System telemetry
│   ├── model_repo.py         # Model repository
│   ├── hardware_detector.py  # Hardware detection
│   ├── log_manager.py        # Logging
│   ├── static/               # Web UI assets
│   └── templates/            # Web UI templates
├── ResultPublisher/          # Result publishing system
│   ├── publisher.py          # Main publisher class
│   ├── base_destination.py   # Base destination class
│   ├── result_destinations.py # Built-in destinations
│   └── plugins/              # Pluggable destinations
│       ├── mqtt_destination.py
│       ├── webhook_destination.py
│       ├── serial_destination.py
│       ├── opcua_destination.py
│       ├── ros2_destination.py
│       ├── zeromq_destination.py
│       ├── folder_destination.py
│       ├── roboflow_destination.py
│       ├── geti_destination.py
│       └── null_destination.py
├── main.py                   # Entry point
├── setup.bat                 # Windows setup script
├── setup.sh                  # Linux/macOS setup script
├── requirements.txt          # Dependencies
├── pyproject.toml            # Project configuration
├── Dockerfile                # Docker container
├── docker-compose.yml        # Docker compose configuration
└── readme.md                 # This file
```

## 🔧 Configuration

The node can be configured through:
- **Command-line arguments**: `python main.py --port 8080 --name "MyNode"`
- **Web UI**: Access the dashboard at `http://localhost:8080`
- **REST API**: Configure via API endpoints

Default settings:
- Node Port: 5555
- Discovery: Enabled
- Telemetry: Disabled by default
- Model Repository: `InferenceNode/model_repository/models/`
- Pipelines: `InferenceNode/pipelines/`

## 🧪 Testing
### TODO 😂


## 🔍 Monitoring and Telemetry

InferNode provides comprehensive system monitoring:

- **CPU usage and frequency**
- **Memory utilization**
- **Disk usage**
- **Network statistics**
- **GPU information (NVIDIA)**
- **Inference performance metrics**

Telemetry data is published to MQTT in JSON format:

```json
{
  "node_id": "uuid-here",
  "timestamp": "2025-07-28T10:30:00Z",
  "cpu": {"usage_percent": 45.2, "count": 8},
  "memory": {"usage_percent": 67.3, "total_gb": 16},
  "gpu": {"available": true, "devices": [...]}
}
```

## 🌐 Network Discovery

Nodes automatically discover each other using UDP broadcasts:

```python
from discovery import NodeDiscovery

# Discover nodes on network
discovered = NodeDiscovery.discover_nodes(timeout=5.0)
for node_id, info in discovered.items():
    print(f"Found node: {node_id} at {info['address']}")
```

## 🔌 Extending the Platform

### Creating Custom Inference Engines

```python
from InferenceEngine.base_engine import BaseInferenceEngine

class MyCustomEngine(BaseInferenceEngine):
    def _load_model(self):
        # Load your model
        pass
    
    def _preprocess(self, image):
        # Preprocess input
        return processed_image
    
    def _infer(self, preprocessed_input):
        # Run inference
        return raw_output
    
    def _postprocess(self, raw_output):
        # Process results
        return final_results
```

### Creating Custom Result Destinations

```python
from ResultPublisher.result_destinations import BaseResultDestination

class MyCustomDestination(BaseResultDestination):
    def configure(self, **kwargs):
        # Configure your destination
        self.is_configured = True
    
    def _publish(self, data):
        # Publish data to your destination
        return True  # Success
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📝 License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## 🆘 Support

For questions and support:
- Create an issue on GitHub
- Check the documentation
- Review the example code

## 🗺️ Roadmap

- [x] Web-based management interface
- [x] Integration with FrameSource library
- [x] Docker containers and orchestration
- [ ] Advanced load balancing
- [ ] Model versioning and A/B testing
- [ ] Enhanced pipeline builder UI
- [ ] Additional inference engine integrations
