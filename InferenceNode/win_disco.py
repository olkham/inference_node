#!/usr/bin/env python3
"""
Windows Device Discovery Service
Makes a device/service discoverable in Windows Explorer under 'This PC'
Similar to SiliconDust HDHomeRun
"""

import socket
import struct
import time
import uuid
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

class DeviceDiscoveryService:
    def __init__(self, device_name="My Custom Device", port=5555, device_uuid=None):
        self.device_name = device_name
        self.device_uuid = device_uuid or str(uuid.uuid4())
        self.local_ip = self.get_local_ip()
        self.http_port = port
        self.running = False
        
        # SSDP Configuration
        self.ssdp_multicast_addr = "239.255.255.250"
        self.ssdp_port = 1900
        
        # Diagnostics
        self.check_firewall()
        self.check_network_interfaces()
        
    def get_local_ip(self):
        """Get the local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def check_firewall(self):
        """Check if Windows Firewall might be blocking"""
        import subprocess
        try:
            print("\n[DIAGNOSTIC] Checking Windows Firewall status...")
            result = subprocess.run(['netsh', 'advfirewall', 'show', 'allprofiles', 'state'], 
                                  capture_output=True, text=True, timeout=5)
            if 'ON' in result.stdout:
                print("[WARNING] Windows Firewall is ON - this may block SSDP traffic")
                print("[INFO] You may need to add firewall rules:")
                print("       1. Allow UDP port 1900 (SSDP)")
                print("       2. Allow TCP port 5555 (HTTP)")
                print("       Or run as Administrator to auto-configure")
        except:
            print("[INFO] Could not check firewall status")
    
    def check_network_interfaces(self):
        """List all network interfaces"""
        import subprocess
        try:
            print("\n[DIAGNOSTIC] Network interfaces:")
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.split('\n')
            for i, line in enumerate(lines):
                if 'IPv4 Address' in line or 'Default Gateway' in line:
                    print(f"  {line.strip()}")
        except:
            print("[INFO] Could not enumerate network interfaces")
    
    def create_ssdp_response(self, st):
        """Create SSDP response message"""
        response = (
            "HTTP/1.1 200 OK\r\n"
            f"CACHE-CONTROL: max-age=1800\r\n"
            f"DATE: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n"
            f"EXT:\r\n"
            f"LOCATION: http://{self.local_ip}:{self.http_port}/device.xml\r\n"
            f"SERVER: Python/3.0 UPnP/1.0 CustomDevice/1.0\r\n"
            f"ST: {st}\r\n"
            f"USN: uuid:{self.device_uuid}::{st}\r\n"
            f"BOOTID.UPNP.ORG: 1\r\n"
            f"CONFIGID.UPNP.ORG: 1\r\n"
            "\r\n"
        )
        return response.encode('utf-8')
    
    def create_ssdp_notify(self, nt):
        """Create SSDP NOTIFY message"""
        notify = (
            "NOTIFY * HTTP/1.1\r\n"
            f"HOST: {self.ssdp_multicast_addr}:{self.ssdp_port}\r\n"
            f"CACHE-CONTROL: max-age=1800\r\n"
            f"LOCATION: http://{self.local_ip}:{self.http_port}/device.xml\r\n"
            f"NT: {nt}\r\n"
            f"NTS: ssdp:alive\r\n"
            f"SERVER: Python/3.0 UPnP/1.0 CustomDevice/1.0\r\n"
            f"USN: uuid:{self.device_uuid}::{nt}\r\n"
            f"BOOTID.UPNP.ORG: 1\r\n"
            f"CONFIGID.UPNP.ORG: 1\r\n"
            "\r\n"
        )
        return notify.encode('utf-8')
    
    def ssdp_listener(self):
        """Listen for SSDP M-SEARCH requests"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # On Windows, also set SO_REUSEPORT if available
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass  # Not available on all systems
            
            # Bind to SSDP port on all interfaces
            try:
                sock.bind(('', self.ssdp_port))
                print(f"[SSDP] Successfully bound to port {self.ssdp_port}")
            except OSError as e:
                print(f"[ERROR] Failed to bind to SSDP port {self.ssdp_port}: {e}")
                print(f"[INFO] Another process may be using this port, or firewall is blocking it")
                return
            
            # Join multicast group on all interfaces
            mreq = struct.pack("4sl", socket.inet_aton(self.ssdp_multicast_addr), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # Also try to join on specific interface
            try:
                mreq_specific = struct.pack("4s4s", socket.inet_aton(self.ssdp_multicast_addr), 
                                          socket.inet_aton(self.local_ip))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq_specific)
                print(f"[SSDP] Joined multicast group on {self.local_ip}")
            except:
                pass
            
            # Set a timeout so we can check self.running periodically
            sock.settimeout(1.0)
            
            print(f"[SSDP] Listening on {self.ssdp_multicast_addr}:{self.ssdp_port}")
        except Exception as e:
            print(f"[ERROR] Failed to setup SSDP listener: {e}")
            return
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode('utf-8', errors='ignore')
                
                if 'M-SEARCH' in message:
                    print(f"[SSDP] M-SEARCH from {addr[0]}:{addr[1]}")
                    
                    # Extract ST (Search Target)
                    st_line = [line for line in message.split('\r\n') if line.startswith('ST:')]
                    if st_line:
                        st = st_line[0].split(':', 1)[1].strip()
                        
                        # Respond to relevant search targets
                        if st in ['ssdp:all', 'upnp:rootdevice', 'urn:schemas-upnp-org:device:Basic:1']:
                            response = self.create_ssdp_response('upnp:rootdevice')
                            sock.sendto(response, addr)
                            print(f"[SSDP] Sent response to {addr[0]}:{addr[1]}")
            except socket.timeout:
                # Normal timeout, just continue
                continue
            except Exception as e:
                if self.running:
                    print(f"[SSDP] Error: {e}")
        
        sock.close()
    
    def ssdp_announcer(self):
        """Periodically announce device presence"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        
        # Set the outgoing interface for multicast
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, 
                          socket.inet_aton(self.local_ip))
            print(f"[SSDP] Announcer using interface: {self.local_ip}")
        except Exception as e:
            print(f"[WARNING] Could not set multicast interface: {e}")
        
        # Announce immediately on startup
        initial_announce = True
        
        while self.running:
            try:
                # Announce different device types
                for nt in ['upnp:rootdevice', f'uuid:{self.device_uuid}', 
                          'urn:schemas-upnp-org:device:Basic:1']:
                    notify = self.create_ssdp_notify(nt)
                    sock.sendto(notify, (self.ssdp_multicast_addr, self.ssdp_port))
                
                if initial_announce:
                    print(f"[SSDP] Initial device announcement sent")
                    initial_announce = False
                else:
                    print(f"[SSDP] Periodic device announcement sent")
                
                time.sleep(30 if initial_announce else 300)  # First announce after 30s, then every 5 minutes
            except Exception as e:
                if self.running:
                    print(f"[SSDP] Announcer error: {e}")
        
        sock.close()
    
    def get_device_description(self):
        """Generate UPnP device description XML (SiliconDust-style)"""
        # Extract last 8 chars of UUID as serial number
        serial = self.device_uuid.replace('-', '')[-8:].upper()
        
        xml = f"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0" xmlns:dlna="urn:schemas-dlna-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<device>
<dlna:X_DLNADOC>DMS-1.50</dlna:X_DLNADOC>
<deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>
<friendlyName>{self.device_name} {serial}</friendlyName>
<presentationURL>http://{self.local_ip}:{self.http_port}/</presentationURL>
<manufacturer>InferenceNode</manufacturer>
<manufacturerURL>https://github.com/olkham/inference_node</manufacturerURL>
<modelDescription>AI Inference Server</modelDescription>
<modelName>{self.device_name}</modelName>
<modelNumber>1.0</modelNumber>
<modelURL>https://github.com/olkham/inference_node</modelURL>
<serialNumber>{serial}</serialNumber>
<UDN>uuid:{self.device_uuid}</UDN>
<serviceList>
<service>
<serviceType>urn:schemas-upnp-org:service:ConnectionManager:1</serviceType>
<serviceId>urn:upnp-org:serviceId:ConnectionManager</serviceId>
<SCPDURL>/xml/ConnectionManager.xml</SCPDURL>
<controlURL>http://{self.local_ip}:{self.http_port}/api/upnp/ConnectionManager</controlURL>
<eventSubURL>http://{self.local_ip}:{self.http_port}/api/upnp/ConnectionManager</eventSubURL>
</service>
<service>
<serviceType>urn:schemas-upnp-org:service:ContentDirectory:1</serviceType>
<serviceId>urn:upnp-org:serviceId:ContentDirectory</serviceId>
<SCPDURL>/xml/ContentDirectory.xml</SCPDURL>
<controlURL>http://{self.local_ip}:{self.http_port}/api/upnp/ContentDirectory</controlURL>
<eventSubURL>http://{self.local_ip}:{self.http_port}/api/upnp/ContentDirectory</eventSubURL>
</service>
</serviceList>
<iconList>
<icon>
<mimetype>image/png</mimetype>
<width>48</width>
<height>48</height>
<depth>24</depth>
<url>/static/images/icon.png</url>
</icon>
<icon>
<mimetype>image/png</mimetype>
<width>120</width>
<height>120</height>
<depth>24</depth>
<url>/static/images/icon.png</url>
</icon>
</iconList>
</device>
</root>"""
        return xml
    
    def get_connection_manager_xml(self):
        """Generate ConnectionManager service description XML"""
        xml = """<?xml version="1.0"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<actionList>
<action>
<name>GetProtocolInfo</name>
<argumentList>
<argument>
<name>Source</name>
<direction>out</direction>
<relatedStateVariable>SourceProtocolInfo</relatedStateVariable>
</argument>
<argument>
<name>Sink</name>
<direction>out</direction>
<relatedStateVariable>SinkProtocolInfo</relatedStateVariable>
</argument>
</argumentList>
</action>
<action>
<name>GetCurrentConnectionIDs</name>
<argumentList>
<argument>
<name>ConnectionIDs</name>
<direction>out</direction>
<relatedStateVariable>CurrentConnectionIDs</relatedStateVariable>
</argument>
</argumentList>
</action>
<action>
<name>GetCurrentConnectionInfo</name>
<argumentList>
<argument>
<name>ConnectionID</name>
<direction>in</direction>
<relatedStateVariable>A_ARG_TYPE_ConnectionID</relatedStateVariable>
</argument>
<argument>
<name>RcsID</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_RcsID</relatedStateVariable>
</argument>
<argument>
<name>AVTransportID</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_AVTransportID</relatedStateVariable>
</argument>
<argument>
<name>ProtocolInfo</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_ProtocolInfo</relatedStateVariable>
</argument>
<argument>
<name>PeerConnectionManager</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_ConnectionManager</relatedStateVariable>
</argument>
<argument>
<name>PeerConnectionID</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_ConnectionID</relatedStateVariable>
</argument>
<argument>
<name>Direction</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_Direction</relatedStateVariable>
</argument>
<argument>
<name>Status</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_ConnectionStatus</relatedStateVariable>
</argument>
</argumentList>
</action>
</actionList>
<serviceStateTable>
<stateVariable sendEvents="yes">
<name>SourceProtocolInfo</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="yes">
<name>SinkProtocolInfo</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="yes">
<name>CurrentConnectionIDs</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_ConnectionStatus</name>
<dataType>string</dataType>
<allowedValueList>
<allowedValue>OK</allowedValue>
<allowedValue>ContentFormatMismatch</allowedValue>
<allowedValue>InsufficientBandwidth</allowedValue>
<allowedValue>UnreliableChannel</allowedValue>
<allowedValue>Unknown</allowedValue>
</allowedValueList>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_ConnectionManager</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_Direction</name>
<dataType>string</dataType>
<allowedValueList>
<allowedValue>Input</allowedValue>
<allowedValue>Output</allowedValue>
</allowedValueList>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_ProtocolInfo</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_ConnectionID</name>
<dataType>i4</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_AVTransportID</name>
<dataType>i4</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_RcsID</name>
<dataType>i4</dataType>
</stateVariable>
</serviceStateTable>
</scpd>"""
        return xml
    
    def get_content_directory_xml(self):
        """Generate ContentDirectory service description XML"""
        xml = """<?xml version="1.0"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<actionList>
<action>
<name>Browse</name>
<argumentList>
<argument>
<name>ObjectID</name>
<direction>in</direction>
<relatedStateVariable>A_ARG_TYPE_ObjectID</relatedStateVariable>
</argument>
<argument>
<name>BrowseFlag</name>
<direction>in</direction>
<relatedStateVariable>A_ARG_TYPE_BrowseFlag</relatedStateVariable>
</argument>
<argument>
<name>Filter</name>
<direction>in</direction>
<relatedStateVariable>A_ARG_TYPE_Filter</relatedStateVariable>
</argument>
<argument>
<name>StartingIndex</name>
<direction>in</direction>
<relatedStateVariable>A_ARG_TYPE_Index</relatedStateVariable>
</argument>
<argument>
<name>RequestedCount</name>
<direction>in</direction>
<relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable>
</argument>
<argument>
<name>SortCriteria</name>
<direction>in</direction>
<relatedStateVariable>A_ARG_TYPE_SortCriteria</relatedStateVariable>
</argument>
<argument>
<name>Result</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_Result</relatedStateVariable>
</argument>
<argument>
<name>NumberReturned</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable>
</argument>
<argument>
<name>TotalMatches</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable>
</argument>
<argument>
<name>UpdateID</name>
<direction>out</direction>
<relatedStateVariable>A_ARG_TYPE_UpdateID</relatedStateVariable>
</argument>
</argumentList>
</action>
<action>
<name>GetSearchCapabilities</name>
<argumentList>
<argument>
<name>SearchCaps</name>
<direction>out</direction>
<relatedStateVariable>SearchCapabilities</relatedStateVariable>
</argument>
</argumentList>
</action>
<action>
<name>GetSortCapabilities</name>
<argumentList>
<argument>
<name>SortCaps</name>
<direction>out</direction>
<relatedStateVariable>SortCapabilities</relatedStateVariable>
</argument>
</argumentList>
</action>
<action>
<name>GetSystemUpdateID</name>
<argumentList>
<argument>
<name>Id</name>
<direction>out</direction>
<relatedStateVariable>SystemUpdateID</relatedStateVariable>
</argument>
</argumentList>
</action>
</actionList>
<serviceStateTable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_SortCriteria</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_UpdateID</name>
<dataType>ui4</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_Filter</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_Result</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_Index</name>
<dataType>ui4</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_ObjectID</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>SortCapabilities</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>SearchCapabilities</name>
<dataType>string</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_Count</name>
<dataType>ui4</dataType>
</stateVariable>
<stateVariable sendEvents="no">
<name>A_ARG_TYPE_BrowseFlag</name>
<dataType>string</dataType>
<allowedValueList>
<allowedValue>BrowseMetadata</allowedValue>
<allowedValue>BrowseDirectChildren</allowedValue>
</allowedValueList>
</stateVariable>
<stateVariable sendEvents="yes">
<name>SystemUpdateID</name>
<dataType>ui4</dataType>
</stateVariable>
</serviceStateTable>
</scpd>"""
        return xml
    
    class DeviceHTTPHandler(BaseHTTPRequestHandler):
        """HTTP handler for device description"""
        
        def __init__(self, *args, service=None, **kwargs):
            self.service = service
            super().__init__(*args, **kwargs)
        
        def do_GET(self):
            if self.path == '/device.xml':
                self.send_response(200)
                self.send_header('Content-Type', 'text/xml')
                self.end_headers()
                self.wfile.write(self.service.get_device_description().encode())
            elif self.path == '/xml/ConnectionManager.xml':
                self.send_response(200)
                self.send_header('Content-Type', 'text/xml')
                self.end_headers()
                self.wfile.write(self.service.get_connection_manager_xml().encode())
            elif self.path == '/xml/ContentDirectory.xml':
                self.send_response(200)
                self.send_header('Content-Type', 'text/xml')
                self.end_headers()
                self.wfile.write(self.service.get_content_directory_xml().encode())
            elif self.path == '/icon.png':
                # Return a simple PNG icon (1x1 transparent pixel as placeholder)
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.end_headers()
                # Minimal transparent PNG
                icon_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x000\x00\x00\x000\x08\x06\x00\x00\x00W\x02\xf9\x87\x00\x00\x00\x19tEXtSoftware\x00Adobe ImageReadyq\xc9e<\x00\x00\x00\x0eIDATx\xda\xed\xc1\x01\x01\x00\x00\x00\x80\x90\xfe\xaf\xee\x08 \x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
                self.wfile.write(icon_data)
            else:
                # Main web interface page
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.service.device_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        .info {{
            margin: 20px 0;
        }}
        .info-item {{
            padding: 10px;
            margin: 10px 0;
            background: #f8f9fa;
            border-left: 4px solid #007bff;
        }}
        .status {{
            display: inline-block;
            padding: 5px 15px;
            background: #28a745;
            color: white;
            border-radius: 20px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{self.service.device_name}</h1>
        <p><span class="status">● Online</span></p>
        
        <div class="info">
            <div class="info-item">
                <strong>Device UUID:</strong> {self.service.device_uuid}
            </div>
            <div class="info-item">
                <strong>IP Address:</strong> {self.service.local_ip}
            </div>
            <div class="info-item">
                <strong>Port:</strong> {self.service.http_port}
            </div>
            <div class="info-item">
                <strong>Device Type:</strong> Basic UPnP Device
            </div>
        </div>
        
        <p>This device is discoverable via UPnP/SSDP and should appear in Windows Explorer under "Other Devices".</p>
    </div>
</body>
</html>"""
                self.wfile.write(html.encode())
        
        def log_message(self, format, *args):
            print(f"[HTTP] {self.address_string()} - {format % args}")
    
    def http_server(self):
        """Run HTTP server for device description"""
        def handler(*args, **kwargs):
            self.DeviceHTTPHandler(*args, service=self, **kwargs)
        
        server = HTTPServer(('0.0.0.0', self.http_port), handler)
        print(f"[HTTP] Server running on http://{self.local_ip}:{self.http_port}")
        
        while self.running:
            server.handle_request()
    
    def add_firewall_rules(self):
        """Attempt to add Windows Firewall rules"""
        import subprocess
        import sys
        
        if not sys.platform.startswith('win'):
            return
        
        print("\n[SETUP] Attempting to configure Windows Firewall...")
        
        try:
            # Add rule for SSDP (UDP 1900)
            cmd_ssdp = [
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name=Python SSDP Discovery',
                'dir=in',
                'action=allow',
                'protocol=UDP',
                'localport=1900',
                'profile=private,public'
            ]
            
            # Add rule for HTTP (TCP 5555)
            cmd_http = [
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name=Python Device HTTP Server',
                'dir=in',
                'action=allow',
                'protocol=TCP',
                'localport=5555',
                'profile=private,public'
            ]
            
            result1 = subprocess.run(cmd_ssdp, capture_output=True, text=True)
            result2 = subprocess.run(cmd_http, capture_output=True, text=True)
            
            if result1.returncode == 0 and result2.returncode == 0:
                print("[SUCCESS] Firewall rules added successfully")
            else:
                print("[INFO] Could not add firewall rules - may need Administrator privileges")
                print("       Run as Administrator or manually add rules for UDP 1900 and TCP 5555")
        except Exception as e:
            print(f"[INFO] Could not configure firewall: {e}")
            print("       You may need to manually add firewall rules")
    
    def start(self):
        """Start the device discovery service"""
        self.running = True
        
        print(f"\nStarting Device Discovery Service")
        print(f"=" * 70)
        print(f"Device Name: {self.device_name}")
        print(f"Device UUID: {self.device_uuid}")
        print(f"Local IP: {self.local_ip}")
        print(f"HTTP Port: {self.http_port}")
        print("=" * 70)
        
        # Try to add firewall rules
        self.add_firewall_rules()
        
        # Start SSDP listener thread
        listener_thread = threading.Thread(target=self.ssdp_listener, daemon=True)
        listener_thread.start()
        
        # Start SSDP announcer thread
        announcer_thread = threading.Thread(target=self.ssdp_announcer, daemon=True)
        announcer_thread.start()
        
        # Start HTTP server thread
        http_thread = threading.Thread(target=self.http_server, daemon=True)
        http_thread.start()
        
        print("\nDevice should now be discoverable in Windows!")
        print("Check 'This PC' or 'Network' in Windows Explorer")
        print("Press Ctrl+C to stop...\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping service...")
            self.running = False


if __name__ == "__main__":
    # Create and start the service
    service = DeviceDiscoveryService(device_name="InferNode", port=5555, device_uuid=None)
    service.start()