"""
Operations Command Center - DLI Web Power Switch REST API Integration
Version: 1.0.0
Last Modified: 2025-01-XX
Author: Billas
Description: DLI Web Power Switch REST API integration for PDU management

File: /modules/ops_center/dli_pdu.py

CHANGELOG:
- 1.0.0 (2025-01-XX): Initial implementation with full REST API support
                      Replaces planned APC unit with DLI Web Power Switch
                      Supports outlet control, monitoring, and automation

NOTES:
- Requires DLI Web Power Switch with REST API enabled
- Uses HTTP Digest Authentication for security
- Designed for DLI Web Power Switch Pro or similar models
- Zero-indexed outlets in REST API (0-7 for 8-outlet model)

FEATURES:
- Individual outlet control (on/off/cycle)
- Real-time power monitoring (amperage)
- Outlet naming and labeling
- AutoPing configuration
- Lua script execution
- Group outlet operations
"""

import requests
from requests.auth import HTTPDigestAuth
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from flask import current_app
import json
import time

class DLIPduAPI:
    """
    DLI Web Power Switch REST API integration.
    
    Provides comprehensive PDU management for Operations Command Center.
    Focuses on outlet control, power monitoring, and automation features.
    """
    
    def __init__(self, host: str = None, username: str = None, password: str = None):
        """
        Initialize DLI PDU API connection.
        
        Args:
            host: DLI PDU IP address (default from config)
            username: API username (default from config)
            password: API password (default from config)
        """
        # Get from config or use provided values
        self.host = host or current_app.config.get('DLI_PDU_HOST', '192.168.1.100')
        self.username = username or current_app.config.get('DLI_PDU_USER', 'admin')
        self.password = password or current_app.config.get('DLI_PDU_PASS', '1234')
        
        # Build base URL
        self.base_url = f"http://{self.host}/restapi"
        
        # Setup HTTP Digest Authentication (more secure than basic auth)
        self.auth = HTTPDigestAuth(self.username, self.password)
        
        # Standard headers for DLI REST API
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-CSRF': 'x'  # Required for state-changing operations
        }
        
        # Get configuration settings
        self.timeout = current_app.config.get('DLI_PDU_TIMEOUT', 10)
        self.verify_ssl = current_app.config.get('DLI_PDU_VERIFY_SSL', False)
        self.outlet_count = current_app.config.get('DLI_PDU_OUTLET_COUNT', 8)
        self.outlet_names = current_app.config.get('DLI_PDU_OUTLET_NAMES', {})
        
        # Simple cache to avoid hammering the API
        self._cache = {}
        self._cache_ttl = current_app.config.get('DLI_PDU_CACHE_TTL', 5)  # seconds
        
    def _api_call(self, method: str, endpoint: str, data: Any = None) -> Optional[Dict]:
        """
        Make REST API call to DLI PDU.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint (e.g., /relay/outlets/0/state/)
            data: Data for POST/PUT/PATCH requests
            
        Returns:
            JSON response or None on error
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Prepare request parameters
            kwargs = {
                'method': method,
                'url': url,
                'auth': self.auth,
                'timeout': self.timeout,
                'verify': self.verify_ssl
            }
            
            # Add headers for all requests
            kwargs['headers'] = self.headers.copy()
            
            # Add data if provided
            if data is not None:
                if method == 'GET':
                    kwargs['params'] = data
                else:
                    # For POST/PUT/PATCH, send as form data or JSON
                    if isinstance(data, dict) and 'value' in data:
                        # Simple value updates use form encoding
                        kwargs['data'] = data
                        kwargs['headers']['Content-Type'] = 'application/x-www-form-urlencoded'
                    else:
                        # Complex data uses JSON
                        kwargs['json'] = data
                        kwargs['headers']['Content-Type'] = 'application/json'
            
            # Make request
            response = requests.request(**kwargs)
            
            # Check response
            if 200 <= response.status_code < 300:
                # Try to parse JSON response
                try:
                    return response.json()
                except (ValueError, json.JSONDecodeError):
                    # Some endpoints return plain text or empty response
                    return {'success': True, 'text': response.text}
            else:
                print(f"[DLI_PDU] API error: {response.status_code} - {response.text[:200]}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"[DLI_PDU] Timeout connecting to {self.host}")
        except requests.exceptions.RequestException as e:
            print(f"[DLI_PDU] Request error: {e}")
        except Exception as e:
            print(f"[DLI_PDU] Unexpected error: {e}")
            
        return None
    
    def get_all_outlets(self) -> List[Dict]:
        """
        Get status of all outlets with details.
        
        Returns:
            List of outlet dictionaries with id, name, state, physical_state, locked
        """
        # Check cache first
        cache_key = 'all_outlets'
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data
        
        outlets = []
        
        # Get states for all outlets using matrix operation
        states = self._api_call('GET', '/relay/outlets/all;/state/')
        physical_states = self._api_call('GET', '/relay/outlets/all;/physical_state/')
        names = self._api_call('GET', '/relay/outlets/all;/name/')
        locked = self._api_call('GET', '/relay/outlets/all;/locked/')
        
        if states and physical_states and names:
            # Process results
            for i in range(self.outlet_count):
                outlet = {
                    'id': i,
                    'number': i + 1,  # Human-friendly numbering (1-8)
                    'name': names[i] if i < len(names) else self.outlet_names.get(i, f'Outlet {i+1}'),
                    'state': states[i] if i < len(states) else False,
                    'physical_state': physical_states[i] if i < len(physical_states) else False,
                    'locked': locked[i] if locked and i < len(locked) else False,
                    'enabled': True  # DLI doesn't have disabled state like MikroTik
                }
                outlets.append(outlet)
        else:
            # Fallback to individual queries if matrix fails
            for i in range(self.outlet_count):
                outlet = self.get_outlet_status(i)
                if outlet:
                    outlets.append(outlet)
        
        # Update cache
        self._cache[cache_key] = (time.time(), outlets)
        
        return outlets
    
    def get_outlet_status(self, outlet_id: int) -> Optional[Dict]:
        """
        Get detailed status for a single outlet.
        
        Args:
            outlet_id: Outlet ID (0-based)
            
        Returns:
            Outlet status dictionary or None
        """
        # Validate outlet ID
        if not 0 <= outlet_id < self.outlet_count:
            print(f"[DLI_PDU] Invalid outlet ID: {outlet_id}")
            return None
        
        # Get individual outlet data
        state = self._api_call('GET', f'/relay/outlets/{outlet_id}/state/')
        physical_state = self._api_call('GET', f'/relay/outlets/{outlet_id}/physical_state/')
        name = self._api_call('GET', f'/relay/outlets/{outlet_id}/name/')
        locked = self._api_call('GET', f'/relay/outlets/{outlet_id}/locked/')
        
        if state is not None and physical_state is not None:
            return {
                'id': outlet_id,
                'number': outlet_id + 1,
                'name': name if name else self.outlet_names.get(outlet_id, f'Outlet {outlet_id+1}'),
                'state': state,
                'physical_state': physical_state,
                'locked': locked if locked is not None else False,
                'enabled': True
            }
        
        return None
    
    def set_outlet_state(self, outlet_id: int, state: bool) -> bool:
        """
        Set outlet state (on/off).
        
        Args:
            outlet_id: Outlet ID (0-based)
            state: True for ON, False for OFF
            
        Returns:
            Success status
        """
        # Validate outlet ID
        if not 0 <= outlet_id < self.outlet_count:
            print(f"[DLI_PDU] Invalid outlet ID: {outlet_id}")
            return False
        
        # Set persistent state (survives reboot)
        result = self._api_call(
            'PUT',
            f'/relay/outlets/{outlet_id}/state/',
            data={'value': 'true' if state else 'false'}
        )
        
        if result:
            # Clear cache
            if 'all_outlets' in self._cache:
                del self._cache['all_outlets']
            print(f"[DLI_PDU] Outlet {outlet_id+1} turned {'ON' if state else 'OFF'}")
            return True
        
        return False
    
    def cycle_outlet(self, outlet_id: int, delay: int = None) -> bool:
        """
        Cycle an outlet (turn off, wait, turn on).
        
        Args:
            outlet_id: Outlet ID (0-based)
            delay: Optional cycle delay in seconds (uses PDU default if not specified)
            
        Returns:
            Success status
        """
        # Validate outlet ID
        if not 0 <= outlet_id < self.outlet_count:
            print(f"[DLI_PDU] Invalid outlet ID: {outlet_id}")
            return False
        
        # Cycle the outlet
        endpoint = f'/relay/outlets/{outlet_id}/cycle/'
        data = {'delay': delay} if delay else None
        
        result = self._api_call('POST', endpoint, data=data)
        
        if result:
            # Clear cache
            if 'all_outlets' in self._cache:
                del self._cache['all_outlets']
            print(f"[DLI_PDU] Outlet {outlet_id+1} cycling...")
            return True
        
        return False
    
    def set_multiple_outlets(self, outlet_states: List[Tuple[int, bool]]) -> bool:
        """
        Set multiple outlets simultaneously.
        
        Args:
            outlet_states: List of (outlet_id, state) tuples
            
        Returns:
            Success status
        """
        # Build the data array for simultaneous switching
        # Format: [[[outlet_id, state], [outlet_id, state], ...]]
        data = [[[oid, state] for oid, state in outlet_states]]
        
        result = self._api_call(
            'POST',
            '/relay/set_outlet_transient_states/',
            data=data
        )
        
        if result:
            # Clear cache
            if 'all_outlets' in self._cache:
                del self._cache['all_outlets']
            print(f"[DLI_PDU] Multiple outlets updated simultaneously")
            return True
        
        return False
    
    def get_power_status(self) -> Optional[Dict]:
            """
            Get current power consumption and status.
            
            Version: 1.0.1
            Updated: 2025-01-XX - Suppress 404 errors for models without current sensors
            
            Returns:
                Dictionary with current_amps, voltage, watts, etc.
            """
            # Note: This endpoint varies by DLI model
            # Some models have current sensors, others don't
            # We'll try common endpoints and return what's available
            
            power_info = {
                'current_amps': 0.0,
                'voltage': 120.0,  # Default US voltage
                'watts': 0.0,
                'max_amps': current_app.config.get('DLI_PDU_MAX_AMPS', 15)
            }
            
            # Try to get current reading (model-dependent)
            # Temporarily suppress error printing for this call
            original_api_call = self._api_call
            
            def quiet_api_call(method, endpoint, data=None):
                """Temporary wrapper to suppress 404 errors"""
                url = f"{self.base_url}{endpoint}"
                try:
                    kwargs = {
                        'method': method,
                        'url': url,
                        'auth': self.auth,
                        'timeout': self.timeout,
                        'verify': self.verify_ssl,
                        'headers': self.headers.copy()
                    }
                    
                    response = requests.request(**kwargs)
                    
                    if 200 <= response.status_code < 300:
                        try:
                            return response.json()
                        except (ValueError, json.JSONDecodeError):
                            return {'success': True, 'text': response.text}
                    elif response.status_code == 404:
                        # Silently return None for 404 (not found)
                        return None
                    else:
                        # Log other errors normally
                        print(f"[DLI_PDU] API error: {response.status_code}")
                        return None
                        
                except Exception:
                    return None
            
            # Try to get current with suppressed 404
            self._api_call = quiet_api_call
            current = self._api_call('GET', '/power/current/')
            self._api_call = original_api_call  # Restore original
            
            if current is not None:
                power_info['current_amps'] = float(current)
                power_info['watts'] = power_info['current_amps'] * power_info['voltage']
            else:
                # Estimate based on outlet states if current sensor not available
                outlets = self.get_all_outlets()
                outlets_on = sum(1 for o in outlets if o.get('physical_state', False))
                # Rough estimate: 1A per outlet (adjust based on your equipment)
                power_info['current_amps'] = outlets_on * 1.0
                power_info['watts'] = power_info['current_amps'] * power_info['voltage']
            
            return power_info
    
    def set_outlet_name(self, outlet_id: int, name: str) -> bool:
        """
        Set custom name for an outlet.
        
        Args:
            outlet_id: Outlet ID (0-based)
            name: New outlet name
            
        Returns:
            Success status
        """
        # Validate outlet ID
        if not 0 <= outlet_id < self.outlet_count:
            print(f"[DLI_PDU] Invalid outlet ID: {outlet_id}")
            return False
        
        result = self._api_call(
            'PUT',
            f'/relay/outlets/{outlet_id}/name/',
            data={'value': name}
        )
        
        if result:
            # Update local config cache
            self.outlet_names[outlet_id] = name
            # Clear cache
            if 'all_outlets' in self._cache:
                del self._cache['all_outlets']
            print(f"[DLI_PDU] Outlet {outlet_id+1} renamed to '{name}'")
            return True
        
        return False
    
    def run_script(self, script_name: str, args: List = None) -> bool:
        """
        Execute a Lua script on the PDU.
        
        Args:
            script_name: Name of the script to run
            args: Optional arguments for the script
            
        Returns:
            Success status
        """
        data = [{'user_function': script_name}]
        
        if args:
            data[0]['args'] = args
        
        result = self._api_call('POST', '/script/start/', data=data)
        
        if result:
            print(f"[DLI_PDU] Script '{script_name}' started")
            return True
        
        return False
    
    def get_autoping_config(self) -> Optional[List[Dict]]:
        """
        Get AutoPing configuration for all monitored IPs.
        
        Returns:
            List of AutoPing configurations
        """
        result = self._api_call('GET', '/autoping/')
        return result if result else None
    
    def test_connection(self) -> bool:
            """
            Test connection to DLI PDU.
            
            Version: 1.0.1
            Updated: 2025-01-XX - Fixed test endpoint for compatibility
            
            Returns:
                True if connection successful, False otherwise
            """
            try:
                # Try to get the state of outlet 0 as a simple test
                # This is more universally supported than /relay/outlets/count/
                result = self._api_call('GET', '/relay/outlets/0/state/')
                if result is not None:
                    print(f"[DLI_PDU] Connection successful to {self.host}")
                    return True
            except Exception as e:
                print(f"[DLI_PDU] Connection test failed: {e}")
            
            return False