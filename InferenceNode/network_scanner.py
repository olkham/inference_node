#!/usr/bin/env python3
"""
Network Discovery Scanner
Discovers UPnP/SSDP devices on the local network
Complements win_disco.py by finding other InferenceNode instances
"""

import socket
import struct
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional
import requests
from urllib.parse import urlparse


class NetworkScanner:
    """Scans network for UPnP/SSDP enabled devices"""
    
    def __init__(self, timeout: int = 3):
        self.timeout = timeout
        self.ssdp_multicast_addr = "239.255.255.250"
        self.ssdp_port = 1900
        self.discovered_devices: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        
    def create_msearch_message(self, search_target: str = "ssdp:all") -> bytes:
        """Create SSDP M-SEARCH discovery message"""
        message = (
            "M-SEARCH * HTTP/1.1\r\n"
            f"HOST: {self.ssdp_multicast_addr}:{self.ssdp_port}\r\n"
            "MAN: \"ssdp:discover\"\r\n"
            f"MX: {self.timeout}\r\n"
            f"ST: {search_target}\r\n"
            "\r\n"
        )
        return message.encode('utf-8')
    
    def parse_ssdp_response(self, data: bytes) -> Optional[Dict]:
        """Parse SSDP response and extract device information"""
        try:
            response = data.decode('utf-8', errors='ignore')
            
            # Parse HTTP-like response
            lines = response.split('\r\n')
            if not lines[0].startswith('HTTP/1.1 200'):
                return None
            
            headers = {}
            for line in lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().upper()] = value.strip()
            
            # Extract key information
            device_info = {
                'location': headers.get('LOCATION', ''),
                'server': headers.get('SERVER', ''),
                'usn': headers.get('USN', ''),
                'st': headers.get('ST', ''),
                'cache_control': headers.get('CACHE-CONTROL', ''),
                'discovered_at': datetime.now().isoformat(),
                'raw_response': response
            }
            
            # Parse UUID from USN
            if 'uuid:' in device_info['usn']:
                uuid_part = device_info['usn'].split('uuid:')[1].split('::')[0]
                device_info['uuid'] = uuid_part
            
            return device_info
            
        except Exception as e:
            print(f"[ERROR] Failed to parse SSDP response: {e}")
            return None
    
    def fetch_device_description(self, location_url: str) -> Optional[Dict]:
        """Fetch and parse device description XML from location URL"""
        try:
            response = requests.get(location_url, timeout=3)
            if response.status_code == 200:
                xml_content = response.text
                
                # Simple XML parsing (could use xml.etree for more robust parsing)
                device_details = {
                    'xml': xml_content,
                    'friendly_name': self._extract_xml_value(xml_content, 'friendlyName'),
                    'manufacturer': self._extract_xml_value(xml_content, 'manufacturer'),
                    'model_name': self._extract_xml_value(xml_content, 'modelName'),
                    'model_description': self._extract_xml_value(xml_content, 'modelDescription'),
                    'serial_number': self._extract_xml_value(xml_content, 'serialNumber'),
                    'presentation_url': self._extract_xml_value(xml_content, 'presentationURL'),
                }
                
                return device_details
        except Exception as e:
            print(f"[WARNING] Could not fetch device description from {location_url}: {e}")
        
        return None
    
    def _extract_xml_value(self, xml: str, tag: str) -> str:
        """Simple XML tag value extraction"""
        try:
            start_tag = f"<{tag}>"
            end_tag = f"</{tag}>"
            start = xml.find(start_tag)
            if start == -1:
                return ""
            start += len(start_tag)
            end = xml.find(end_tag, start)
            if end == -1:
                return ""
            return xml[start:end].strip()
        except:
            return ""
    
    def scan(self, search_target: str = "ssdp:all", max_wait: int = None) -> List[Dict]:
        """
        Perform network scan for UPnP/SSDP devices
        
        Args:
            search_target: SSDP search target (ssdp:all, upnp:rootdevice, etc.)
            max_wait: Maximum time to wait for responses (uses self.timeout if None)
        
        Returns:
            List of discovered device information dictionaries
        """
        if max_wait is None:
            max_wait = self.timeout
        
        print(f"\n[SCAN] Starting network discovery scan...")
        print(f"[SCAN] Search Target: {search_target}")
        print(f"[SCAN] Timeout: {max_wait} seconds")
        print("-" * 70)
        
        # Create UDP socket for multicast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(max_wait)
        
        # Send M-SEARCH message
        message = self.create_msearch_message(search_target)
        try:
            sock.sendto(message, (self.ssdp_multicast_addr, self.ssdp_port))
            print(f"[SCAN] M-SEARCH sent to {self.ssdp_multicast_addr}:{self.ssdp_port}")
        except Exception as e:
            print(f"[ERROR] Failed to send M-SEARCH: {e}")
            sock.close()
            return []
        
        # Collect responses
        devices = {}
        start_time = time.time()
        response_count = 0
        
        while time.time() - start_time < max_wait:
            try:
                data, addr = sock.recvfrom(2048)
                response_count += 1
                
                print(f"[SCAN] Response #{response_count} from {addr[0]}:{addr[1]}")
                
                device_info = self.parse_ssdp_response(data)
                if device_info:
                    # Use location URL as unique key
                    location = device_info['location']
                    if location and location not in devices:
                        devices[location] = device_info
                        devices[location]['ip_address'] = addr[0]
                        
                        # Try to fetch detailed device description
                        details = self.fetch_device_description(location)
                        if details:
                            devices[location].update(details)
                        
                        print(f"[FOUND] Device: {device_info.get('friendly_name', 'Unknown')}")
                        print(f"        Location: {location}")
                        print(f"        Server: {device_info['server']}")
                        print("-" * 70)
                
            except socket.timeout:
                # Normal timeout when no more responses
                break
            except Exception as e:
                print(f"[ERROR] Error receiving response: {e}")
                continue
        
        sock.close()
        
        print(f"\n[SCAN] Discovery complete!")
        print(f"[SCAN] Found {len(devices)} unique device(s)")
        
        # Store in class attribute
        with self.lock:
            self.discovered_devices = devices
        
        return list(devices.values())
    
    def scan_for_infernodes(self) -> List[Dict]:
        """Specifically scan for InferenceNode devices"""
        print("\n[INFERNODE SCAN] Searching for InferenceNode devices...")
        
        # Do multiple scans with different search targets
        all_devices = {}
        
        for st in ['ssdp:all', 'upnp:rootdevice', 'urn:schemas-upnp-org:device:Basic:1']:
            devices = self.scan(search_target=st, max_wait=2)
            for device in devices:
                location = device.get('location', '')
                if location:
                    all_devices[location] = device
        
        # Filter for InferenceNode devices
        infernodes = []
        for device in all_devices.values():
            friendly_name = device.get('friendly_name', '').lower()
            model_name = device.get('model_name', '').lower()
            
            if 'infernode' in friendly_name or 'infernode' in model_name:
                infernodes.append(device)
        
        print(f"\n[INFERNODE SCAN] Found {len(infernodes)} InferenceNode(s)")
        return infernodes
    
    def monitor_network(self, interval: int = 30, callback=None):
        """
        Continuously monitor network for devices
        
        Args:
            interval: Seconds between scans
            callback: Optional callback function called with device list after each scan
        """
        print(f"\n[MONITOR] Starting continuous network monitoring (interval: {interval}s)")
        print("[MONITOR] Press Ctrl+C to stop...\n")
        
        try:
            while True:
                devices = self.scan_for_infernodes()
                
                if callback:
                    callback(devices)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[MONITOR] Monitoring stopped")
    
    def get_discovered_devices(self) -> Dict[str, Dict]:
        """Get dictionary of all discovered devices"""
        with self.lock:
            return self.discovered_devices.copy()
    
    def print_device_summary(self, device: Dict):
        """Print a formatted summary of a device"""
        print("\n" + "=" * 70)
        print(f"Device: {device.get('friendly_name', 'Unknown Device')}")
        print("=" * 70)
        print(f"  IP Address:     {device.get('ip_address', 'N/A')}")
        print(f"  Location:       {device.get('location', 'N/A')}")
        print(f"  UUID:           {device.get('uuid', 'N/A')}")
        print(f"  Manufacturer:   {device.get('manufacturer', 'N/A')}")
        print(f"  Model:          {device.get('model_name', 'N/A')}")
        print(f"  Description:    {device.get('model_description', 'N/A')}")
        print(f"  Server:         {device.get('server', 'N/A')}")
        
        presentation_url = device.get('presentation_url', '')
        if presentation_url:
            print(f"  Web Interface:  {presentation_url}")
        
        print(f"  Discovered:     {device.get('discovered_at', 'N/A')}")
        print("=" * 70)


class InferenceNodeCluster:
    """Manages a cluster of discovered InferenceNode instances"""
    
    def __init__(self):
        self.scanner = NetworkScanner()
        self.nodes: Dict[str, Dict] = {}
        
    def discover_nodes(self) -> List[Dict]:
        """Discover all InferenceNode instances on the network"""
        nodes = self.scanner.scan_for_infernodes()
        
        # Update nodes dictionary
        for node in nodes:
            location = node.get('location', '')
            if location:
                self.nodes[location] = node
        
        return nodes
    
    def get_node_status(self, node: Dict) -> Optional[Dict]:
        """Get status information from an InferenceNode via its REST API"""
        try:
            presentation_url = node.get('presentation_url', '')
            if not presentation_url:
                return None
            
            # Parse base URL
            parsed = urlparse(presentation_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # Try to get node info from REST API
            response = requests.get(f"{base_url}/api/node/info", timeout=3)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[WARNING] Could not get status from node: {e}")
        
        return None
    
    def list_nodes(self):
        """Print a list of all discovered nodes"""
        if not self.nodes:
            print("\n[CLUSTER] No InferenceNode instances discovered")
            return
        
        print(f"\n[CLUSTER] Discovered {len(self.nodes)} InferenceNode instance(s):")
        print("=" * 70)
        
        for i, (location, node) in enumerate(self.nodes.items(), 1):
            name = node.get('friendly_name', 'Unknown')
            ip = node.get('ip_address', 'N/A')
            url = node.get('presentation_url', 'N/A')
            
            print(f"\n{i}. {name}")
            print(f"   IP:  {ip}")
            print(f"   URL: {url}")
            
            # Try to get additional status
            status = self.get_node_status(node)
            if status:
                print(f"   Status: {status.get('status', 'Unknown')}")
                if 'pipelines' in status:
                    print(f"   Pipelines: {len(status['pipelines'])}")
        
        print("\n" + "=" * 70)


def main():
    """Main entry point for network scanner"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Network Discovery Scanner for InferenceNode devices'
    )
    parser.add_argument(
        '--mode',
        choices=['scan', 'infernode', 'monitor', 'cluster'],
        default='infernode',
        help='Scan mode: scan (all devices), infernode (InferenceNode only), monitor (continuous), cluster (manage nodes)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=3,
        help='Timeout in seconds for device responses (default: 3)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Interval in seconds for monitor mode (default: 30)'
    )
    parser.add_argument(
        '--search-target',
        default='ssdp:all',
        help='SSDP search target (default: ssdp:all)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Network Discovery Scanner")
    print("=" * 70)
    
    if args.mode == 'scan':
        # Scan for all UPnP devices
        scanner = NetworkScanner(timeout=args.timeout)
        devices = scanner.scan(search_target=args.search_target)
        
        print(f"\n\nDiscovered {len(devices)} device(s):\n")
        for device in devices:
            scanner.print_device_summary(device)
    
    elif args.mode == 'infernode':
        # Scan specifically for InferenceNode devices
        scanner = NetworkScanner(timeout=args.timeout)
        nodes = scanner.scan_for_infernodes()
        
        print(f"\n\nDiscovered {len(nodes)} InferenceNode(s):\n")
        for node in nodes:
            scanner.print_device_summary(node)
    
    elif args.mode == 'monitor':
        # Continuous monitoring
        scanner = NetworkScanner(timeout=args.timeout)
        
        def print_summary(devices):
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(devices)} device(s)")
            for device in devices:
                name = device.get('friendly_name', 'Unknown')
                ip = device.get('ip_address', 'N/A')
                print(f"  - {name} ({ip})")
        
        scanner.monitor_network(interval=args.interval, callback=print_summary)
    
    elif args.mode == 'cluster':
        # Cluster management
        cluster = InferenceNodeCluster()
        print("\n[CLUSTER] Discovering InferenceNode instances...")
        cluster.discover_nodes()
        cluster.list_nodes()
    
    print("\n[DONE] Scan complete\n")


if __name__ == "__main__":
    main()
