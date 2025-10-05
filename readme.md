# InferNode - Scalable Inference Platform

InferNode is a scalable inference platform that provides multi-node management and control for AI/ML inference workloads. It enables easy deployment and management of inference pipelines across distributed nodes with auto-discovery, telemetry, and flexible result publishing.

## 🚀 Features

### Core Capabilities
- **Multi-engine support**: Ultralytics YOLO, Geti, PyTorch, and custom engines
- **Auto-discovery**: Nodes automatically discover each other on the network
- **Real-time telemetry**: System monitoring and performance metrics via MQTT
- **Flexible result publishing**: MQTT, webhooks, serial, and custom destinations
- **RESTful API**: Complete HTTP API for remote management
- **Rate limiting**: Built-in rate limiting for all result destinations

### Supported Inference Engines
- **Ultralytics**: YOLO object detection models
- **Geti**: Intel's computer vision platform
- **PyTorch**: General PyTorch model support
- **Custom**: Extensible framework for custom implementations

### Result Destinations
- **MQTT**: Publish results to MQTT brokers
- **Webhook**: HTTP POST to custom endpoints
- **Serial**: Output to serial ports
- **Custom**: Implement your own destinations

## 📋 Requirements

- Python 3.8+
- Compatible with Windows, Linux, and macOS
- Optional: CUDA for GPU acceleration
- Optional: MQTT broker for telemetry

## 🛠️ Installation

### Quick Start
```bash
# Clone the repository
git clone <repository-url>
cd InferNode

# Run the setup script
python setup.py
```

### Manual Installation
```bash
# Install core dependencies
pip install -r requirements.txt

# Optional: Install AI/ML frameworks
pip install torch torchvision ultralytics

# Optional: Install GPU monitoring
pip install pynvml

# Optional: Install serial communication
pip install pyserial
```

## 🏃‍♂️ Quick Start

### 1. Start an Inference Node
```python
from InferenceNode import InferenceNode

# Create and start a node
node = InferenceNode("MyNode", port=5000)
node.start(enable_discovery=True, enable_telemetry=True)
```

Or use the command line:
```bash
# Start full node with all services
python main.py

# Start web interface only
python main.py --web-only

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
InferNode/
├── InferenceEngine/          # Inference engine implementations
│   ├── __init__.py
│   ├── base_engine.py        # Base class for all engines
│   ├── ultralytics_engine.py # Ultralytics YOLO support
│   ├── geti_engine.py        # Geti support
│   ├── torch_engine.py       # PyTorch model support
│   └── custom_engine.py      # Custom engine template
├── ResultPublisher/          # Result publishing system
│   ├── __init__.py
│   ├── publisher.py          # Main publisher class
│   └── result_destinations.py # Destination implementations
├── tests/                    # Unit tests
├── inference_node.py         # Main node implementation
├── telemetry.py             # System telemetry
├── discovery.py             # Network discovery
├── example.py               # Usage examples
├── setup.py                 # Installation script
├── requirements.txt         # Dependencies
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## 🔧 Configuration

Create a `config.py` file (see `config_example.py`):

```python
# Node configuration
NODE_NAME = "MyInferNode"
NODE_PORT = 5000

# MQTT configuration
MQTT_SERVER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "infernode"

# Discovery configuration
DISCOVERY_PORT = 8888
ENABLE_DISCOVERY = True

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "logs/infernode.log"
```

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_inference_engine.py

# Run with coverage
python -m pytest --cov=InferenceEngine --cov=ResultPublisher tests/
```

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

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions and support:
- Create an issue on GitHub
- Check the documentation
- Review the example code

## 🗺️ Roadmap

- [ ] Web-based management interface
- [ ] Database integration for model management
- [ ] Kubernetes deployment support
- [ ] Advanced load balancing
- [ ] Model versioning and A/B testing
- [ ] Integration with FrameSource library
- [ ] Docker containers and orchestration
