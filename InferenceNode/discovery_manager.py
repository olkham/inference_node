#!/usr/bin/env python3
"""
InferNode Discovery Manager

Integrated discovery service for finding and managing other InferNode instances on the network.
This replaces the separate discovery server and integrates directly into the main InferenceNode application.
"""

import json
import socket
import threading
import time
import requests
import concurrent.futures
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Try to import zeroconf for mDNS support
try:
    from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser, ServiceListener as ZeroconfServiceListener
    MDNS_AVAILABLE = True
    # Use the real ServiceListener from zeroconf
    ServiceListenerBase = ZeroconfServiceListener
except ImportError:
    MDNS_AVAILABLE = False
    # Create dummy base class if zeroconf not available
    class ServiceListenerBase:  # type: ignore
        """Dummy ServiceListener base class when zeroconf is not available"""
        pass


class MDNSServiceListener(ServiceListenerBase):  # type: ignore
    """Listener for mDNS service discovery events"""
    
    def __init__(self, discovery_manager):
        self.discovery_manager = discovery_manager
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def add_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is discovered"""
        if not MDNS_AVAILABLE:
            return
        info = zc.get_service_info(service_type, name)
        if info:
            self._process_service_info(info, name)
    
    def update_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is updated"""
        if not MDNS_AVAILABLE:
            return
        info = zc.get_service_info(service_type, name)
        if info:
            self._process_service_info(info, name)
    
    def remove_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is removed"""
        # Extract node_id from service name
        node_id = name.split('.')[0] if '.' in name else name
        if node_id in self.discovery_manager.discovered_nodes:
            node_name = self.discovery_manager.discovered_nodes[node_id].node_name
            self.discovery_manager.discovered_nodes[node_id].mark_offline()
            self.logger.info(f"mDNS service removed: {node_name} ({node_id})")
    
    def _process_service_info(self, info, name: str):
        """Process discovered service information"""
        try:
            # Filter for InferNode services only (service name starts with "InferNode-")
            if not name.startswith('InferNode-'):
                return
            
            # Extract properties from mDNS service
            properties = {}
            if info.properties:
                for key, value in info.properties.items():
                    try:
                        properties[key.decode('utf-8')] = value.decode('utf-8')
                    except:
                        pass
            
            # Only process if this is an InferNode service (has node_id property)
            if 'node_id' not in properties:
                return
            
            # Get IP address
            if info.addresses:
                ip_address = socket.inet_ntoa(info.addresses[0])
            else:
                self.logger.warning(f"No IP address for service {name}")
                return
            
            port = info.port
            node_id = properties.get('node_id', name.split('-')[1].split('.')[0] if '-' in name else name.split('.')[0])
            
            # Skip our own service
            if node_id == self.discovery_manager.node_id:
                return
            
            # Build node data from mDNS properties
            node_data = {
                'node_id': node_id,
                'node_name': properties.get('node_name', 'Unknown Node'),
                'api_port': port,
                'platform': properties.get('platform', 'Unknown'),
                'cpu_count': int(properties.get('cpu_count', 0)),
                'memory_gb': float(properties.get('memory_gb', 0)),
                'available_engines': json.loads(properties.get('available_engines', '[]')),
                'gpu': json.loads(properties.get('gpu', '{"available": false}'))
            }
            
            # Add or update discovered node
            if node_id in self.discovery_manager.discovered_nodes:
                self.discovery_manager.discovered_nodes[node_id].update_status()
                self.logger.debug(f"Updated mDNS node: {node_id} at {ip_address}:{port}")
            else:
                self.discovery_manager.discovered_nodes[node_id] = DiscoveredNode(
                    node_data, ip_address, port
                )
                self.logger.info(f"Discovered mDNS node: {node_data['node_name']} ({node_id}) at {ip_address}:{port}")
                
                # Probe the new node for detailed information
                threading.Thread(
                    target=self.discovery_manager._probe_node,
                    args=(node_id,),
                    daemon=True
                ).start()
        
        except Exception as e:
            self.logger.error(f"Error processing mDNS service {name}: {str(e)}")


class MDNSBroadcaster:
    """Handles mDNS service broadcasting for node discovery"""
    
    def __init__(self, node_id: str, node_info: Dict[str, Any], service_port: int):
        """
        Initialize mDNS broadcaster
        
        Args:
            node_id: Unique identifier for this node
            node_info: Dictionary containing node information
            service_port: Port number where the service is running
        """
        self.node_id = node_id
        self.node_info = node_info
        self.service_port = service_port
        self.zeroconf = None
        self.service_info = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.running = False
        
        if not MDNS_AVAILABLE:
            self.logger.warning("zeroconf package not available. mDNS broadcasting disabled.")
            self.logger.info("Install with: pip install zeroconf")
    
    def start(self):
        """Start mDNS service broadcasting"""
        if not MDNS_AVAILABLE:
            self.logger.warning("Cannot start mDNS: zeroconf package not installed")
            return False
        
        if self.running:
            self.logger.warning("mDNS broadcaster already running")
            return True
        
        try:
            from zeroconf import Zeroconf, ServiceInfo
            
            self.zeroconf = Zeroconf()
            
            # Service type for InferNode discovery (using standard HTTP service type)
            service_type = "_http._tcp.local."
            service_name = f"InferNode-{self.node_id}.{service_type}"
            
            # Get local IP address (using the same method as network scan to get actual network IP)
            try:
                # Connect to external address to determine local network IP
                temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                temp_sock.connect(("8.8.8.8", 80))
                local_ip = temp_sock.getsockname()[0]
                temp_sock.close()
            except Exception as e:
                # Fallback to hostname resolution if the above fails
                self.logger.warning(f"Failed to get network IP via connection test: {e}")
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
            
            hostname = socket.gethostname()
            
            # Prepare service properties
            properties = {
                'node_id': self.node_id,
                'node_name': self.node_info.get('node_name', 'Unknown Node'),
                'platform': self.node_info.get('platform', 'Unknown'),
                'cpu_count': str(self.node_info.get('cpu_count', 0)),
                'memory_gb': str(self.node_info.get('memory_gb', 0)),
                'available_engines': json.dumps(self.node_info.get('available_engines', [])),
                'gpu': json.dumps(self.node_info.get('gpu', {'available': False}))
            }
            
            # Create service info
            self.service_info = ServiceInfo(
                service_type,
                service_name,
                addresses=[socket.inet_aton(local_ip)],
                port=self.service_port,
                properties=properties,
                server=f"{hostname}.local."
            )
            
            # Register service
            self.zeroconf.register_service(self.service_info)
            self.running = True
            
            self.logger.info(f"mDNS service registered: {service_name} on {local_ip}:{self.service_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start mDNS broadcaster: {str(e)}")
            return False
    
    def stop(self):
        """Stop mDNS service broadcasting"""
        if not self.running:
            return
        
        try:
            if self.zeroconf and self.service_info:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
            
            self.running = False
            self.logger.info("mDNS service unregistered")
            
        except Exception as e:
            self.logger.error(f"Error stopping mDNS broadcaster: {str(e)}")
    
    def update_info(self, node_info: Dict[str, Any]):
        """Update node information and re-register service"""
        self.node_info = node_info
        if self.running:
            self.stop()
            self.start()


class DiscoveredNode:
    """Information about a discovered inference node"""
    
    def __init__(self, node_data: Dict[str, Any], ip_address: str, port: int):
        self.node_id = node_data.get('node_id', 'unknown')
        self.node_name = node_data.get('node_name', 'Unknown Node')
        self.ip_address = ip_address
        self.port = port
        self.platform = node_data.get('platform', 'Unknown')
        self.cpu_count = node_data.get('cpu_count', 0)
        self.memory_gb = node_data.get('memory_gb', 0)
        self.available_engines = node_data.get('available_engines', [])
        self.gpu = node_data.get('gpu', {'available': False})
        self.last_seen = datetime.now()
        self.status = 'online'
        self.response_time = 0
        self.capabilities = node_data
        # Additional information fetched during probing
        self.pipeline_info: Optional[Dict[str, Any]] = None
        self.system_metrics: Optional[Dict[str, Any]] = None
        # Use the JSON info endpoint for API probing
        self.api_url = f"http://{ip_address}:{port}/api/info"
        
    def update_status(self, response_time: Optional[float] = None):
        """Update node status and last seen time"""
        self.last_seen = datetime.now()
        self.status = 'online'
        if response_time is not None:
            self.response_time = response_time
            
    def mark_offline(self):
        """Mark node as offline"""
        self.status = 'offline'
        
    def is_stale(self, timeout_minutes: int = 5) -> bool:
        """Check if node hasn't been seen for too long"""
        return datetime.now() - self.last_seen > timedelta(minutes=timeout_minutes)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'node_id': self.node_id,
            'node_name': self.node_name,
            'ip_address': self.ip_address,
            'port': self.port,
            'platform': self.platform,
            'cpu_count': self.cpu_count,
            'memory_gb': self.memory_gb,
            'available_engines': self.available_engines,
            'gpu': self.gpu,
            'last_seen': self.last_seen.isoformat(),
            'status': self.status,
            'response_time': self.response_time,
            'url': f"http://{self.ip_address}:{self.port}",
            'api_url': f"http://{self.ip_address}:{self.port}/api/info"
        }
        
        # Add pipeline information if available
        if self.pipeline_info:
            result['pipeline_info'] = self.pipeline_info
        
        # Add system metrics if available
        if self.system_metrics:
            result['system_metrics'] = self.system_metrics
            
        return result


class DiscoveryManager:
    """Manages discovery of other InferNode instances on the network"""
    
    def __init__(self, discovery_port: int = 8888, node_id: Optional[str] = None, node_info: Optional[Dict[str, Any]] = None):
        self.discovery_port = discovery_port
        self.node_id = node_id
        self.node_info = node_info or {}
        self.discovered_nodes: Dict[str, DiscoveredNode] = {}
        self.discovery_running = False
        self.discovery_thread = None
        self.broadcast_thread = None
        self.broadcast_interval = 10.0  # seconds
        
        # mDNS components
        self.mdns_broadcaster = None
        self.mdns_browser = None
        self.mdns_listener = None
        self.zeroconf = None
        self.use_mdns = MDNS_AVAILABLE  # Enable mDNS if available
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if MDNS_AVAILABLE:
            self.logger.info(f"Discovery Manager initialized on port {self.discovery_port} with mDNS support")
        else:
            self.logger.info(f"Discovery Manager initialized on port {self.discovery_port} (UDP only - install zeroconf for mDNS)")
    
    def set_node_info(self, node_id: str, node_info: Dict[str, Any]):
        """Set the node information for broadcasting"""
        self.node_id = node_id
        self.node_info = node_info
        self.logger.debug(f"Node info updated for discovery: {node_info.get('node_name', 'Unknown')} ({node_id})")
        
        # Update mDNS broadcaster if it exists
        if self.mdns_broadcaster:
            self.mdns_broadcaster.update_info(node_info)
    
    def set_broadcast_interval(self, interval: float):
        """Set the broadcast interval in seconds"""
        self.broadcast_interval = interval
        self.logger.info(f"Broadcast interval set to {interval} seconds")
    
    def start_discovery(self):
        """Start UDP discovery service"""
        if self.discovery_running:
            self.logger.warning("Discovery already running")
            return
        
        self.discovery_running = True
        
        # Start UDP listener thread
        self.discovery_thread = threading.Thread(target=self._discovery_worker, daemon=True)
        self.discovery_thread.start()
        
        # Start mDNS if available and we have node info
        if self.use_mdns and self.node_id and self.node_info:
            self._start_mdns()
        
        # Start broadcast thread if we have node info to broadcast
        if self.node_id and self.node_info:
            self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
            self.broadcast_thread.start()
            mode = "mDNS + UDP" if self.use_mdns else "UDP"
            self.logger.info(f"Started node discovery with {mode} broadcasting on port {self.discovery_port}")
        else:
            self.logger.info(f"Started node discovery (listening only) on port {self.discovery_port}")
    
    def stop_discovery(self):
        """Stop discovery service"""
        self.discovery_running = False
        
        # Stop mDNS
        self._stop_mdns()
        
        if self.discovery_thread:
            self.discovery_thread.join(timeout=2)
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=2)
        self.logger.info("Stopped node discovery")
    
    def _start_mdns(self):
        """Start mDNS service broadcasting and browsing"""
        if not MDNS_AVAILABLE or not self.node_id:
            return
        
        try:
            from zeroconf import Zeroconf, ServiceBrowser
            
            # Start mDNS broadcaster
            api_port = self.node_info.get('api_port', 5000)
            self.mdns_broadcaster = MDNSBroadcaster(self.node_id, self.node_info, api_port)
            if self.mdns_broadcaster.start():
                self.logger.info("mDNS broadcaster started")
            
            # Start mDNS browser to discover other nodes
            self.zeroconf = Zeroconf()
            self.mdns_listener = MDNSServiceListener(self)
            self.mdns_browser = ServiceBrowser(
                self.zeroconf,
                "_http._tcp.local.",
                self.mdns_listener
            )
            self.logger.info("mDNS browser started")
            
        except Exception as e:
            self.logger.error(f"Failed to start mDNS: {str(e)}")
    
    def _stop_mdns(self):
        """Stop mDNS service broadcasting and browsing"""
        try:
            if self.mdns_broadcaster:
                self.mdns_broadcaster.stop()
                self.mdns_broadcaster = None
            
            if self.mdns_browser:
                self.mdns_browser.cancel()
                self.mdns_browser = None
            
            if self.zeroconf:
                self.zeroconf.close()
                self.zeroconf = None
            
            if self.mdns_listener:
                self.mdns_listener = None
                
        except Exception as e:
            self.logger.error(f"Error stopping mDNS: {str(e)}")
    
    def _discovery_worker(self):
        """UDP discovery worker thread"""
        sock = None
        last_refresh = time.time()
        refresh_interval = 30  # Refresh node information every 30 seconds
        
        try:
            # Create UDP socket for discovery
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)  # 1 second timeout
            
            # Increase receive buffer size to handle large hardware info messages
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            
            # Bind to discovery port
            sock.bind(('', self.discovery_port))
            self.logger.info(f"Discovery service listening on UDP port {self.discovery_port}")
            
            while self.discovery_running:
                try:
                    # Listen for discovery announcements (increased buffer for hardware details)
                    data, addr = sock.recvfrom(8192)
                    self._handle_discovery_message(data, addr)
                    
                except socket.timeout:
                    # Check for stale nodes periodically
                    self._cleanup_stale_nodes()
                    
                    # Refresh node information periodically
                    current_time = time.time()
                    if current_time - last_refresh > refresh_interval:
                        self.refresh_all_nodes()
                        last_refresh = current_time
                    
                    continue
                except Exception as e:
                    if self.discovery_running:
                        self.logger.error(f"Discovery error: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Failed to start discovery service: {str(e)}")
        finally:
            if sock:
                sock.close()
            self.logger.info("Discovery service stopped")
    
    def _broadcast_loop(self):
        """Periodically broadcast node presence"""
        while self.discovery_running:
            try:
                self._send_broadcast()
                time.sleep(self.broadcast_interval)
            except Exception as e:
                self.logger.error(f"Broadcast error: {str(e)}")
                time.sleep(self.broadcast_interval)
    
    def _send_broadcast(self):
        """Send broadcast announcement"""
        if not self.node_id or not self.node_info:
            return
            
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            announcement = {
                'type': 'node_announcement',
                'node_id': self.node_id,
                'node_info': self.node_info,
                'timestamp': time.time()
            }
            
            data = json.dumps(announcement).encode('utf-8')
            
            # Send to broadcast address only (more efficient and reduces duplicates)
            try:
                sock.sendto(data, ('255.255.255.255', self.discovery_port))
                self.logger.debug(f"Broadcast announcement sent: {self.node_info.get('node_name')} ({self.node_id}) on port {self.node_info.get('api_port')}")
            except Exception as e:
                self.logger.debug(f"Failed to broadcast: {e}")
                # Fallback to local broadcast
                try:
                    sock.sendto(data, ('<broadcast>', self.discovery_port))
                    self.logger.debug(f"Fallback broadcast sent: {self.node_info.get('node_name')} ({self.node_id})")
                except Exception as e2:
                    self.logger.error(f"All broadcast methods failed: {e2}")
            
        except Exception as e:
            self.logger.error(f"Broadcast send error: {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    def _handle_discovery_message(self, data: bytes, addr: tuple):
        """Handle incoming discovery message"""
        try:
            message = json.loads(data.decode('utf-8'))
            
            if message.get('type') == 'node_announcement':
                node_data = message.get('node_info', {})
                ip_address = addr[0]
                port = node_data.get('api_port', 5000)
                node_id = node_data.get('node_id')
                
                # Skip our own announcements
                if node_id == self.node_id:
                    self.logger.debug(f"Ignoring our own announcement from {addr[0]}")
                    return
                
                if node_id:
                    if node_id in self.discovered_nodes:
                        # Update existing node (but don't log every update to reduce noise)
                        self.discovered_nodes[node_id].update_status()
                        self.logger.debug(f"Updated existing node: {node_id} from {addr[0]}")
                    else:
                        # Add new node
                        self.discovered_nodes[node_id] = DiscoveredNode(node_data, ip_address, port)
                        self.logger.info(f"Discovered new node: {node_data.get('node_name', 'Unknown')} ({node_id}) at {ip_address}:{port}")
                        
                        # Probe the new node for detailed information
                        threading.Thread(target=self._probe_node, args=(node_id,), daemon=True).start()
            
            elif message.get('type') == 'discovery_request':
                self.logger.debug(f"Received discovery request from {addr[0]}")
                # Respond with our node information if we have it
                if self.node_id and self.node_info:
                    self._send_discovery_response(addr)
                
        except Exception as e:
            self.logger.error(f"Failed to parse discovery message from {addr}: {str(e)}")
    
    def _send_discovery_response(self, addr: tuple):
        """Send discovery response to a specific address"""
        if not self.node_id or not self.node_info:
            return
            
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            response = {
                'type': 'discovery_response',
                'node_id': self.node_id,
                'node_info': self.node_info,
                'timestamp': time.time()
            }
            
            data = json.dumps(response).encode('utf-8')
            sock.sendto(data, addr)
            self.logger.debug(f"Sent discovery response to {addr}")
            
        except Exception as e:
            self.logger.error(f"Failed to send discovery response to {addr}: {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    def _probe_node(self, node_id: str):
        """Probe a node for detailed information"""
        if node_id not in self.discovered_nodes:
            return
        
        node = self.discovered_nodes[node_id]
        try:
            start_time = time.time()
            response = requests.get(node.api_url, timeout=5)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                detailed_info = response.json()
                
                # Update basic node information with fresh data
                if 'node_name' in detailed_info:
                    node.node_name = detailed_info['node_name']
                if 'platform' in detailed_info:
                    node.platform = detailed_info['platform']
                if 'cpu_count' in detailed_info:
                    node.cpu_count = detailed_info['cpu_count']
                if 'memory_gb' in detailed_info:
                    node.memory_gb = detailed_info['memory_gb']
                if 'available_engines' in detailed_info:
                    node.available_engines = detailed_info['available_engines']
                if 'hardware' in detailed_info:
                    # Update GPU information from hardware data
                    hardware = detailed_info['hardware']
                    
                    # Calculate total GPU count from all vendors
                    nvidia_count = hardware.get('nvidia', {}).get('gpu_count', 0)
                    intel_count = len(hardware.get('intel', {}).get('gpu_devices', []))
                    amd_count = 1 if hardware.get('amd', {}).get('gpu') else 0
                    apple_count = 1 if hardware.get('apple', {}).get('gpu') else 0
                    
                    total_gpu_count = nvidia_count + intel_count + amd_count + apple_count
                    
                    node.gpu = {
                        'available': total_gpu_count > 0,
                        'count': total_gpu_count,
                        'details': hardware
                    }
                
                # Update node with detailed information
                node.capabilities = detailed_info
                
                # Get pipeline information
                try:
                    pipeline_response = requests.get(f"http://{node.ip_address}:{node.port}/api/pipelines/summary", timeout=3)
                    if pipeline_response.status_code == 200:
                        node.pipeline_info = pipeline_response.json()
                    else:
                        node.pipeline_info = None
                except:
                    node.pipeline_info = None
                
                # Get system metrics (if available)
                try:
                    metrics_response = requests.get(f"http://{node.ip_address}:{node.port}/api/node/info", timeout=3)
                    if metrics_response.status_code == 200:
                        metrics_data = metrics_response.json()
                        # Extract relevant metrics
                        node.system_metrics = {
                            'cpu_usage': metrics_data.get('system_metrics', {}).get('cpu_usage', 0),
                            'memory_usage': metrics_data.get('system_metrics', {}).get('memory_usage', 0)
                        }
                    else:
                        node.system_metrics = None
                except:
                    node.system_metrics = None
                
                node.update_status(response_time)
                self.logger.info(f"Probed node {node_id} ({node.node_name}): {response_time:.1f}ms response time")
            else:
                node.mark_offline()
                
        except Exception as e:
            self.logger.warning(f"Failed to probe node {node_id}: {str(e)}")
            node.mark_offline()
    
    def refresh_all_nodes(self):
        """Refresh information for all online nodes"""
        for node_id, node in list(self.discovered_nodes.items()):
            if node.status == 'online':
                self._probe_node(node_id)
    
    def _cleanup_stale_nodes(self):
        """Remove nodes that haven't been seen for too long"""
        stale_nodes = [node_id for node_id, node in self.discovered_nodes.items() if node.is_stale()]
        
        for node_id in stale_nodes:
            node_name = self.discovered_nodes[node_id].node_name
            del self.discovered_nodes[node_id]
            self.logger.info(f"Removed stale node: {node_name} ({node_id})")
    
    def scan_network(self):
        """Actively scan network for nodes"""
        self.logger.info("Starting active network scan...")
        
        # Get local network range
        try:
            # Get local IP to determine network range
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            sock.close()
            
            # Simple scan of common ports on local subnet
            ip_parts = local_ip.split('.')
            base_ip = '.'.join(ip_parts[:3])
            
            def scan_ip(ip):
                for port in [5000, 5001, 5002, 5555, 8000, 8080]:
                    try:
                        response = requests.get(f"http://{ip}:{port}/api/info", timeout=2)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('node_id'):
                                # Found an InferNode
                                node_id = data['node_id']
                                if node_id not in self.discovered_nodes:
                                    self.discovered_nodes[node_id] = DiscoveredNode(data, ip, port)
                                    self.logger.info(f"Network scan found node: {data.get('node_name', 'Unknown')} at {ip}:{port}")
                                break
                    except:
                        continue
            
            # Scan local subnet (last 50 IPs)
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for i in range(1, 51):
                    ip = f"{base_ip}.{i}"
                    if ip != local_ip:  # Don't scan ourselves
                        futures.append(executor.submit(scan_ip, ip))
                        
                # Wait for all scans to complete
                concurrent.futures.wait(futures, timeout=30)
            
            self.logger.info(f"Network scan completed. Found {len(self.discovered_nodes)} nodes total.")
            
        except Exception as e:
            self.logger.error(f"Network scan failed: {str(e)}")
    
    def get_discovered_nodes(self) -> List[Dict[str, Any]]:
        """Get list of all discovered nodes"""
        return [node.to_dict() for node in self.discovered_nodes.values()]
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get specific node information"""
        if node_id not in self.discovered_nodes:
            return None
        
        node = self.discovered_nodes[node_id]
        # Try to get fresh info from the node
        try:
            response = requests.get(node.api_url, timeout=5)
            if response.status_code == 200:
                fresh_data = response.json()
                return fresh_data
        except:
            pass
        
        return node.to_dict()
    
    def control_node(self, node_id: str, action: str) -> Dict[str, Any]:
        """Control node operations (ping, etc.)"""
        if node_id not in self.discovered_nodes:
            return {'error': 'Node not found'}
        
        node = self.discovered_nodes[node_id]
        
        try:
            if action == 'ping':
                # Ping the node
                start_time = time.time()
                response = requests.get(node.api_url, timeout=5)
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    node.update_status(response_time)
                    return {
                        'status': 'success',
                        'response_time': response_time,
                        'message': f'Node responded in {response_time:.1f}ms'
                    }
                else:
                    node.mark_offline()
                    return {'error': f'Node responded with status {response.status_code}'}
            
            else:
                return {'error': f'Unknown action: {action}'}
                
        except Exception as e:
            self.logger.error(f"Control action failed for {node_id}: {str(e)}")
            return {'error': str(e)}