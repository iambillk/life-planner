"""
Operations Command Center - External System Integrations
Version: 1.0.0
Last Modified: 2024-01-XX
Author: Billas
Description: Integration classes leveraging existing network module

File: /modules/ops_center/integrations.py

CHANGELOG:
- 1.0.0 (2024-01-XX): Initial implementation using existing LibreNMS functions
"""

from flask import current_app
import requests


class OpsLibreNMS:
    """
    LibreNMS integration for Operations Command Center.
    Uses existing LibreNMS functionality from network module.
    """
    
    def __init__(self):
        """Initialize with Flask app config."""
        self.base_url = current_app.config.get('LIBRENMS_BASE_URL', '').rstrip('/')
        self.api_token = current_app.config.get('LIBRENMS_API_TOKEN', '')
        
    def librenms_api_call(self, endpoint):
        """
        Make LibreNMS API call - same pattern as network module.
        
        Args:
            endpoint: API endpoint
            
        Returns:
            JSON response or None
        """
        if not self.base_url or not self.api_token:
            return None
            
        headers = {'X-Auth-Token': self.api_token}
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
        
    def get_device_stats(self):
        """Get device statistics from LibreNMS."""
        data = self.librenms_api_call('/api/v0/devices')
        
        if not data or 'devices' not in data:
            return {'status': 'OPERATIONAL', 'devices_up': 0, 'devices_down': 0}
            
        devices = data['devices']
        up = sum(1 for d in devices if d.get('status') == 1)
        down = len(devices) - up
        
        return {
            'status': 'OPERATIONAL' if down == 0 else 'DEGRADED',
            'devices_up': up,
            'devices_down': down,
            'total_devices': len(devices)
        }
        
    def get_wan_bandwidth(self):
        """Get WAN stats - real status, mock bandwidth for now."""
        stats = self.get_device_stats()
        
        return {
            'wan1': {
                'status': 'UP' if stats['devices_down'] == 0 else 'DEGRADED',
                'download_mbps': 487,
                'upload_mbps': 122,
                'uptime_percent': 99.2
            },
            'wan2': {
                'status': 'UP',
                'download_mbps': 94,
                'upload_mbps': 18,
                'uptime_percent': 99.8
            }
        }
        
    def get_alert_summary(self):
        """Get LibreNMS alerts."""
        data = self.librenms_api_call('/api/v0/alerts')
        
        if not data or 'alerts' not in data:
            return {'total': 0, 'critical': 0, 'warning': 0, 'latest': 'No alerts'}
            
        alerts = data['alerts']
        
        return {
            'total': len(alerts),
            'critical': sum(1 for a in alerts if a.get('severity') == 'critical'),
            'warning': sum(1 for a in alerts if a.get('severity') == 'warning'),
            'latest': alerts[0].get('name', 'Alert') if alerts else 'No alerts'
        }

    def get_port_graphs(self):
        """
        Generate graph URLs for WAN ports.
        
        Returns:
            dict: Graph URLs for embedding as images
        """
        # Graph dimensions for dashboard
        width = 400
        height = 100
        time_period = '-6h'  # Last x hours
        
        # WAN port IDs from LibreNMS
        wan1_port_id = 272
        wan2_port_id = 273
        
        graph_base = f"{self.base_url}/graph.php"
        
        return {
            'wan1_graph': f"{graph_base}?type=port_bits&id={wan1_port_id}&from={time_period}&width={width}&height={height}&auth_token={self.api_token}",
            'wan2_graph': f"{graph_base}?type=port_bits&id={wan2_port_id}&from={time_period}&width={width}&height={height}&auth_token={self.api_token}"
        }

    def get_port_bandwidth(self):
        """
        Get current bandwidth utilization for WAN ports.
        
        Returns:
            dict: Current bandwidth in Mbps for WAN1 and WAN2
        """
        # Get port data from LibreNMS API
        wan1_data = self.librenms_api_call('/api/v0/ports/272')
        wan2_data = self.librenms_api_call('/api/v0/ports/273')
        
        wan_stats = {}
        
        # Process WAN1
        if wan1_data and 'port' in wan1_data:
            port = wan1_data['port'][0] if isinstance(wan1_data['port'], list) else wan1_data['port']
            # Convert bps to Mbps (bits per second / 1,000,000)
            wan_stats['wan1'] = {
                'status': 'UP' if port.get('ifOperStatus') == 'up' else 'DOWN',
                'download_mbps': round(port.get('ifInOctets_rate', 0) * 8 / 1000000, 1),
                'upload_mbps': round(port.get('ifOutOctets_rate', 0) * 8 / 1000000, 1),
                'port_name': port.get('ifName', 'WAN1')
            }
        else:
            # Fallback to mock if API fails
            wan_stats['wan1'] = {
                'status': 'UP',
                'download_mbps': 487,
                'upload_mbps': 122,
                'port_name': 'WAN1'
            }
        
        # Process WAN2
        if wan2_data and 'port' in wan2_data:
            port = wan2_data['port'][0] if isinstance(wan2_data['port'], list) else wan2_data['port']
            wan_stats['wan2'] = {
                'status': 'UP' if port.get('ifOperStatus') == 'up' else 'DOWN',
                'download_mbps': round(port.get('ifInOctets_rate', 0) * 8 / 1000000, 1),
                'upload_mbps': round(port.get('ifOutOctets_rate', 0) * 8 / 1000000, 1),
                'port_name': port.get('ifName', 'WAN2')
            }
        else:
            # Fallback to mock if API fails
            wan_stats['wan2'] = {
                'status': 'UP',
                'download_mbps': 94,
                'upload_mbps': 18,
                'port_name': 'WAN2'
            }
        
        return wan_stats

    def get_ips_alerts(self):
        """
        Get IPS alerts from OPNsense via LibreNMS syslog with analytics.
        
        Returns:
            dict: IPS alert count, analytics, and recent alerts
        """
        from datetime import datetime, timedelta
        import re
        
        now = datetime.now()
        yesterday = now - timedelta(hours=24)
        
        from_time = yesterday.strftime('%Y-%m-%d %H:%M:%S')
        to_time = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # Get 24 hours of logs
        syslog_data = self.librenms_api_call(f'/api/v0/logs/syslog/2?from={from_time}&to={to_time}&limit=5000')
        
        if not syslog_data or 'logs' not in syslog_data:
            return {'count': 0, 'latest': 'No IPS alerts', 'recent_alerts': []}
        
        # Process IPS alerts with analytics
        ips_alerts = []
        attack_types = {}
        source_ips = {}
        target_ports = {}
        
        for log in syslog_data.get('logs', []):
            msg = log.get('msg', '')
            if 'SURICATA' in msg or '[Drop]' in msg or '[Alert]' in msg:
                alert = {
                    'timestamp': log.get('timestamp'),
                    'message': msg,
                    'priority': log.get('priority')
                }
                ips_alerts.append(alert)
                
                # Extract attack type
                if 'ET ' in msg:
                    attack_match = re.search(r'ET\s+(\w+)', msg)
                    if attack_match:
                        attack_type = attack_match.group(1)
                        attack_types[attack_type] = attack_types.get(attack_type, 0) + 1
                
                # Extract source IP
                ip_match = re.search(r'\{TCP\}\s+([\d\.]+):', msg)
                if ip_match:
                    src_ip = ip_match.group(1)
                    source_ips[src_ip] = source_ips.get(src_ip, 0) + 1
        
        # Get top attackers
        top_attackers = sorted(source_ips.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Get latest alert
        latest = 'No IPS alerts'
        if ips_alerts:
            latest_msg = ips_alerts[0]['message']
            if 'ET ' in latest_msg:
                parts = latest_msg.split('ET ')
                if len(parts) > 1:
                    threat = parts[1].split('[')[0].strip()
                    latest = threat[:50]
        
        return {
            'count': len(ips_alerts),
            'latest': latest,
            'recent_alerts': ips_alerts[:50],
            'analytics': {
                '24hr_total': len(ips_alerts),
                'attack_types': dict(attack_types),
                'top_attackers': top_attackers,
                'hourly_rate': round(len(ips_alerts) / 24, 1)
            }
        }
    def get_ip_whois(self, ip_address):
        """
        Get WHOIS information using local whois.exe tool.
        
        Args:
            ip_address: IP to lookup
            
        Returns:
            dict: WHOIS data from local whois tool
        """
        import subprocess
        
        try:
            # Path to whois.exe - adjust if needed
            whois_path = r'C:\Users\wgkish\whois.exe'
            
            # Run whois.exe with the IP
            result = subprocess.run(
                [whois_path, ip_address],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout:
                output = result.stdout
                
                # Initialize data
                data = {
                    'ip': ip_address,
                    'country': 'Unknown',
                    'org': 'Unknown',
                    'network': 'Unknown',
                    'cidr': 'Unknown',
                    'owner': 'Unknown',
                    'address': 'Unknown',
                    'abuse_email': 'Unknown',
                    'contact': 'Unknown',
                    'phone': 'Unknown'
                }
                
                # Parse line by line
                lines = output.split('\n')
                for line in lines:
                    if ':' in line:
                        # Split only on first colon to preserve address format
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            
                            # Map the whois fields to our data structure
                            if key == 'IP Address':
                                continue  # Skip, we already have it
                            elif key == 'Country':
                                data['country'] = value
                            elif key == 'Network Name':
                                data['network'] = value
                            elif key == 'Owner Name':
                                data['owner'] = value
                                data['org'] = value
                            elif key == 'CIDR':
                                data['cidr'] = value
                            elif key == 'Contact Name':
                                data['contact'] = value
                            elif key == 'Address':
                                data['address'] = value  # This should now capture the full address
                            elif key == 'Abuse Email':
                                data['abuse_email'] = value
                            elif key == 'Email':
                                if data['abuse_email'] == 'Unknown':
                                    data['abuse_email'] = value
                            elif key == 'Phone' and value:
                                data['phone'] = value
                
                return data
                
        except subprocess.TimeoutExpired:
            print(f"[OPS CENTER] WHOIS timeout for {ip_address}")
        except FileNotFoundError:
            print("[OPS CENTER] whois.exe not found at specified path")
        except Exception as e:
            print(f"[OPS CENTER] WHOIS error for {ip_address}: {e}")
        
        # Fallback if whois.exe fails
        return {
            'ip': ip_address,
            'country': 'Lookup failed',
            'org': 'Unknown',
            'network': 'Unknown',
            'cidr': 'Unknown',
            'owner': 'Unknown',
            'address': 'Unknown',
            'abuse_email': 'Unknown',
            'contact': 'Unknown',
            'phone': 'Unknown'
        }