"""
Operations Command Center - MikroTik REST API Integration
Version: 1.0.1
Last Modified: 2024-01-XX
Author: Billas
Description: MikroTik RouterOS v7 REST API integration for CRS354-48G switch management

File: /modules/ops_center/mikrotik.py

CHANGELOG:
- 1.0.1 (2024-01-XX): Fixed port status detection using 'running' field
- 1.0.0 (2024-01-XX): Initial implementation with basic port status/control

NOTES:
- Requires RouterOS v7.1+ for REST API support
- Uses basic auth for simplicity (consider tokens for production)
- Designed specifically for CRS354-48G-4S+2Q+ switch
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app
import base64
import json

class MikroTikAPI:
    """
    MikroTik RouterOS v7 REST API integration.
    
    Provides simplified switch management for Operations Command Center.
    Focus on port status, bandwidth monitoring, and basic control.
    """
    
    def __init__(self, host: str = None, username: str = None, password: str = None):
        """
        Initialize MikroTik API connection.
        
        Args:
            host: MikroTik IP address (default from config)
            username: API username (default from config)
            password: API password (default from config)
        """
        # Get from config or use provided values
        self.host = host or current_app.config.get('MIKROTIK_HOST', '192.168.1.1')
        self.username = username or current_app.config.get('MIKROTIK_USER', 'admin')
        self.password = password or current_app.config.get('MIKROTIK_PASS', '')
        
        # Build base URL and auth header
        self.base_url = f"http://{self.host}/rest"
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {encoded}',
            'Content-Type': 'application/json'
        }
        
        # Simple cache to avoid hammering the API
        self._cache = {}
        self._cache_ttl = 30  # seconds
        
    def _api_call(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """
        Make REST API call to MikroTik.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint (e.g., /interface/ethernet)
            data: JSON data for POST/PUT/PATCH requests
            
        Returns:
            JSON response or None on error
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Make request with SSL verification disabled for internal switches
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=10,
                verify=False  # Internal switch, self-signed cert
            )
            
            if 200 <= response.status_code < 300:
                # Some endpoints may return empty body
                if not response.content:
                    return {'success': True}
                # Only parse JSON if the content type is JSON
                ctype = response.headers.get('Content-Type', '').lower()
                if 'application/json' in ctype:
                    try:
                        return response.json()
                    except Exception:
                        return {'success': True}
                # Treat as success if no JSON body
                return {'success': True}
            else:
                print(f"[MIKROTIK] API error: {response.status_code} - {response.text[:400]}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"[MIKROTIK] Timeout connecting to {self.host}")
        except Exception as e:
            print(f"[MIKROTIK] Error: {e}")
            
        return None
    
    def get_all_ports(self) -> List[Dict]:
        """
        Get all ethernet ports including SFP/QSFP with their current status.
        
        Returns:
            List of port dictionaries with status, speed, errors
        """
        # Check cache first
        cache_key = 'all_ports'
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).seconds < self._cache_ttl:
                return cached_data
        
        # Get interface data
        interfaces = self._api_call('GET', '/interface/ethernet')
        
        if not interfaces:
            # Return mock data if API fails
            return self._get_mock_ports()
        
        # Process ports for dashboard display
        ports = []
        raw = interfaces['data'] if isinstance(interfaces, dict) and 'data' in interfaces else interfaces
        for iface in raw:
            port_num = None
            port_name = iface['name']
            
            # Handle regular ethernet ports (ether1 through ether48)
            if port_name.startswith('ether'):
                try:
                    port_num = int(port_name.replace('ether', ''))
                    if port_num > 48:  # Skip if it's beyond regular ports
                        continue
                except:
                    continue
                interface_type = 'ethernet'
            
            # Handle SFP+ ports (sfp-sfpplus1 through sfp-sfpplus4)
            elif port_name.startswith('sfp-sfpplus'):
                try:
                    sfp_num = int(port_name.replace('sfp-sfpplus', ''))
                    port_num = 48 + sfp_num  # IDs 49-52
                except:
                    continue
                interface_type = 'sfp'
            
            # Handle QSFP+ main ports only (qsfpplus1-1 and qsfpplus2-1)
            elif port_name.startswith('qsfpplus'):
                try:
                    parts = port_name.replace('qsfpplus', '').split('-')
                    if len(parts) == 2:
                        qsfp_main = int(parts[0])  # 1 or 2
                        qsfp_sub = int(parts[1])   # 1, 2, 3, or 4
                        # Only include the first sub-interface (-1) as the main port
                        if qsfp_sub == 1:
                            port_num = 52 + qsfp_main  # IDs 53-54
                        else:
                            continue  # Skip sub-interfaces 2, 3, 4
                except:
                    continue
                interface_type = 'qsfp'
            
            # Skip if we couldn't determine port number
            if not port_num:
                continue
            
            # Handle string or boolean disabled field
            disabled = iface.get('disabled', False)
            if isinstance(disabled, str):
                disabled = disabled.lower() == 'true'
            
            # Handle running field (link status) as string or boolean
            running = iface.get('running', False)
            if isinstance(running, str):
                running = running.lower() == 'true'
            elif not isinstance(running, bool):
                running = False
            
            rx_err = int(iface.get('rx-error', 0) or 0)
            tx_err = int(iface.get('tx-error', 0) or 0)

            port_data = {
                'id': port_num,
                'name': iface.get('comment', f"Port {port_num}" if port_num <= 48 else port_name),
                'status': 'up' if running else 'down',  # Link status
                'enabled': not disabled,  # Administrative status
                'speed': iface.get('speed', 'Unknown'),
                'rx_bytes': int(iface.get('rx-byte', 0) or 0),
                'tx_bytes': int(iface.get('tx-byte', 0) or 0),
                'rx_errors': rx_err,
                'tx_errors': tx_err,
                'has_errors': (rx_err + tx_err) > 0,
                'interface_type': interface_type
            }
            ports.append(port_data)
        
        # Sort by port number
        ports.sort(key=lambda x: x['id'])
        
        # Cache the results
        self._cache[cache_key] = (datetime.now(), ports)
        
        return ports[:54]  # 48 ethernet + 4 SFP + 2 QSFP
    
    def get_port_details(self, port_id: int) -> Optional[Dict]:
        """
        Get detailed info for a specific port.
        
        Args:
            port_id: Port number (1-54)
            
        Returns:
            Detailed port information including traffic stats
        """
        # Determine the correct interface name based on port_id
        if port_id <= 48:
            port_name = f"ether{port_id}"
        elif port_id <= 52:  # SFP+ ports 49-52
            sfp_num = port_id - 48
            port_name = f"sfp-sfpplus{sfp_num}"
        elif port_id <= 54:  # QSFP+ ports 53-54
            qsfp_num = port_id - 52
            port_name = f"qsfpplus{qsfp_num}-1"  # Using main interface
        else:
            return None
        
        # Get interface details
        iface = self._api_call('GET', f'/interface/ethernet/{port_name}')
        
        if not iface:
            return None
        
        # Handle string or boolean disabled field
        disabled = iface.get('disabled', False)
        if isinstance(disabled, str):
            disabled = disabled.lower() == 'true'
        
        # Handle running field (link status) as string or boolean
        running = iface.get('running', False)
        if isinstance(running, str):
            running = running.lower() == 'true'
        elif not isinstance(running, bool):
            running = False
        
        # Get traffic monitoring data
        traffic = self._api_call('POST', '/interface/monitor-traffic', {
            'interface': port_name,
            'once': True
        })
        
        rx_bps = tx_bps = 0
        if traffic:
            # RouterOS may return [ { ... } ] or { ... }
            payload = traffic[0] if isinstance(traffic, list) and traffic else traffic
            try:
                rx_bps = int(payload.get('rx-bits-per-second', 0) or 0)
                tx_bps = int(payload.get('tx-bits-per-second', 0) or 0)
            except Exception:
                rx_bps = tx_bps = 0
        
        return {
            'id': port_id,
            'name': iface.get('comment', f"Port {port_id}" if port_id <= 48 else port_name),
            'status': 'up' if running else 'down',
            'enabled': not disabled,
            'speed': iface.get('speed', 'Unknown'),
            'mac_address': iface.get('mac-address', 'Unknown'),
            'rx_bytes': iface.get('rx-byte', 0),
            'tx_bytes': iface.get('tx-byte', 0),
            'rx_rate_bps': rx_bps,
            'tx_rate_bps': tx_bps,
            'rx_mbps': round(rx_bps / 1_000_000, 2),
            'tx_mbps': round(tx_bps / 1_000_000, 2),
            'rx_errors': iface.get('rx-error', 0),
            'tx_errors': iface.get('tx-error', 0)
        }
    
    def toggle_port(self, port_id: int, enable: bool) -> bool:
        """
        Enable or disable a port.
        
        Args:
            port_id: Port number (1-54)
            enable: True to enable, False to disable
            
        Returns:
            Success status
        """
        # Determine the correct interface name
        if port_id <= 48:
            port_name = f"ether{port_id}"
        elif port_id <= 52:
            sfp_num = port_id - 48
            port_name = f"sfp-sfpplus{sfp_num}"
        elif port_id <= 54:
            qsfp_num = port_id - 52
            port_name = f"qsfpplus{qsfp_num}-1"
        else:
            return False
        
        # Try PATCH first for partial update
        result = self._api_call('PATCH', f'/interface/ethernet/{port_name}', {
            'disabled': not enable
        })
        if not result:
            # Fallback to PUT
            result = self._api_call('PUT', f'/interface/ethernet/{port_name}', {
                'disabled': not enable
            })
        
        # Clear cache after change
        if 'all_ports' in self._cache:
            del self._cache['all_ports']
            
        return result is not None
    
    def set_port_name(self, port_id: int, name: str) -> bool:
        """
        Set port comment/description.
        
        Args:
            port_id: Port number (1-54)
            name: New description for the port
            
        Returns:
            Success status
        """
        # Determine the correct interface name
        if port_id <= 48:
            port_name = f"ether{port_id}"
        elif port_id <= 52:
            sfp_num = port_id - 48
            port_name = f"sfp-sfpplus{sfp_num}"
        elif port_id <= 54:
            qsfp_num = port_id - 52
            port_name = f"qsfpplus{qsfp_num}-1"
        else:
            return False
        
        # Read current admin state so we don't accidentally enable/disable on rename
        iface = self._api_call('GET', f'/interface/ethernet/{port_name}')
        if not iface:
            return False
        
        disabled = iface.get('disabled', False)
        if isinstance(disabled, str):
            disabled = disabled.lower() == 'true'
        
        # Prefer PATCH for partial update (RouterOS v7); fallback to PUT preserving 'disabled'
        result = self._api_call('PATCH', f'/interface/ethernet/{port_name}', {
            'comment': name
        })
        if not result:
            # Fallback: preserve disabled flag explicitly
            result = self._api_call('PUT', f'/interface/ethernet/{port_name}', {
                'comment': name,
                'disabled': disabled
            })
        
        # Clear cache
        if 'all_ports' in self._cache:
            del self._cache['all_ports']
            
        return result is not None
    
    def _get_mock_ports(self) -> List[Dict]:
        """
        Return mock port data for testing without API access.
        
        Returns:
            List of 48 mock ports
        """
        import random
        
        ports = []
        for i in range(1, 49):
            status = 'up' if random.random() > 0.15 else 'down'
            has_errors = random.random() < 0.05
            
            ports.append({
                'id': i,
                'name': f"Port {i}",
                'status': status,
                'enabled': True,
                'speed': '1Gbps' if i <= 48 else '10Gbps',
                'rx_bytes': random.randint(1000000, 9999999999),
                'tx_bytes': random.randint(1000000, 9999999999),
                'rx_errors': random.randint(0, 100) if has_errors else 0,
                'tx_errors': random.randint(0, 50) if has_errors else 0,
                'has_errors': has_errors
            })
            
        return ports
