"""
Operations Command Center - Routes
Version: 1.1.0
Last Modified: 2024-01-XX
Author: Billas
Description: All routes for Operations Command Center module

File: /modules/ops_center/routes.py

CHANGELOG:
- 1.1.0 (2024-01-XX): Added MikroTik switch integration
- 1.0.0 (2024-01-XX): Initial implementation with mock data
"""

from flask import Blueprint, render_template, jsonify
from datetime import datetime
import random
from modules.ops_center.integrations import OpsLibreNMS
from modules.ops_center.mikrotik import MikroTikAPI  # NEW IMPORT

# Create blueprint with url_prefix
ops_center_bp = Blueprint('ops_center', __name__, url_prefix='/ops')

@ops_center_bp.route('/')
def dashboard():
    """
    Main dashboard view for Operations Command Center.
    Displays unified monitoring interface for all infrastructure.
    
    Returns:
        Rendered HTML template with dashboard
    """
    # Initialize LibreNMS integration
    libre = OpsLibreNMS()
    
    # Initialize MikroTik integration - NEW
    mikrotik = MikroTikAPI()
    
    # Get real LibreNMS data
    device_stats = libre.get_device_stats()
    wan_stats = libre.get_port_bandwidth()
    alert_summary = libre.get_alert_summary()
    graph_urls = libre.get_port_graphs()
    ips_alerts = libre.get_ips_alerts()  # Get real IPS alerts
    
    # Get MikroTik switch data - NEW
    switch_ports = mikrotik.get_all_ports()
    
    # Calculate switch statistics - NEW
    switch_stats = {
        'total_ports': len(switch_ports),
        'ports_up': sum(1 for p in switch_ports if p['status'] == 'up'),
        'ports_down': sum(1 for p in switch_ports if p['status'] == 'down'),
        'ports_errors': sum(1 for p in switch_ports if p.get('has_errors', False))
    }
    
    # Build context with mix of real and mock data
    context = {
        'page_title': 'Operations Command Center',
        'last_refresh': datetime.now().strftime('%H:%M:%S'),
        'system_status': device_stats['status'],
        
        # WAN data - now with REAL bandwidth
        'wan1': wan_stats['wan1'],
        'wan2': wan_stats['wan2'],
        
        # Graph URLs for embedding
        'wan1_graph_url': graph_urls['wan1_graph'],
        'wan2_graph_url': graph_urls['wan2_graph'],
        
        # Alerts - NOW WITH REAL IPS DATA!
        'alerts': {
            'ips_count': ips_alerts['count'],  # REAL IPS from OPNsense syslog
            'ips_latest': ips_alerts['latest'],  # REAL IPS alert message
            'firewalla_count': 1,  # Still mock
            'firewalla_latest': 'Port Scan',  # Still mock
            'syslogs_count': alert_summary['warning'],  # LibreNMS warnings
            'hostmon_downtime': '4min @3am'  # Still mock
        },
        
        # PDU stays the same for now...
        'pdu': {
            'name': 'PDU-1',
            'current_amps': 8.2,
            'max_amps': 15,
            'outlets': [
                {'id': i, 'on': i != 3, 'name': f'Outlet-{i}'} 
                for i in range(1, 11)
            ]
        },
        
        # OLD switch display - keeping for backwards compatibility
        'switches': [
            {'name': 'MikroTik', 'ports': 24, 'active': 18},
            {'name': 'Zyxel-1', 'ports': 48, 'active': 42},
            {'name': 'Zyxel-2', 'ports': 24, 'active': 20}
        ],
        
        # NEW MikroTik switch data for grid display
        'mikrotik_switch': {
            'model': 'CRS354-48G-4S+2Q+',
            'ports': switch_ports,
            'stats': switch_stats
        },
        
        'device_stats': device_stats
    }
    
    return render_template('ops_center/dashboard.html', **context)

@ops_center_bp.route('/api/refresh')
def api_refresh():
    """
    API endpoint for dashboard auto-refresh via AJAX.
    Called every 30 seconds by dashboard JavaScript.
    
    Returns:
        JSON response with updated metrics
    """
    # Get real LibreNMS data for refresh
    libre = OpsLibreNMS()
    alert_summary = libre.get_alert_summary()
    wan_stats = libre.get_port_bandwidth()
    ips_alerts = libre.get_ips_alerts()
    
    # Get MikroTik data for refresh - NEW
    mikrotik = MikroTikAPI()
    switch_ports = mikrotik.get_all_ports()
    switch_stats = {
        'ports_up': sum(1 for p in switch_ports if p['status'] == 'up'),
        'total_ports': len(switch_ports)
    }
    
    # Return real data
    return jsonify({
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'wan1_down': wan_stats['wan1']['download_mbps'],
        'wan1_up': wan_stats['wan1']['upload_mbps'],
        'wan2_down': wan_stats['wan2']['download_mbps'],
        'wan2_up': wan_stats['wan2']['upload_mbps'],
        'ips_count': ips_alerts['count'],  # REAL IPS count
        'pdu_amps': round(random.uniform(7.5, 9.5), 1),  # Still mock
        'switch_ports_up': switch_stats['ports_up'],  # NEW
        'switch_total_ports': switch_stats['total_ports']  # NEW
    })

@ops_center_bp.route('/api/ips-details')
def api_ips_details():
    """
    Get detailed IPS alerts with analytics for modal display.
    
    Returns:
        JSON response with recent IPS alerts and 24-hour analytics
    """
    libre = OpsLibreNMS()
    ips_data = libre.get_ips_alerts()
    
    return jsonify({
        'count': ips_data['count'],
        'alerts': ips_data.get('recent_alerts', []),
        'analytics': ips_data.get('analytics', {})  # Include the analytics data
    })

@ops_center_bp.route('/api/whois/<ip>')
def api_whois_lookup(ip):
    """
    Perform WHOIS lookup on an IP address.
    
    Args:
        ip: IP address to lookup
        
    Returns:
        JSON response with WHOIS data
    """
    libre = OpsLibreNMS()
    whois_data = libre.get_ip_whois(ip)
    
    return jsonify(whois_data)

# ============ NEW MIKROTIK ROUTES ============

@ops_center_bp.route('/api/switch/port/<int:port_id>')
def api_switch_port_details(port_id):
    """
    Get detailed information for a specific switch port.
    
    Args:
        port_id: Port number (1-48)
        
    Returns:
        JSON response with port details including traffic stats
    """
    mikrotik = MikroTikAPI()
    port_data = mikrotik.get_port_details(port_id)
    
    if not port_data:
        return jsonify({'error': 'Port not found'}), 404
    
    # Convert bytes to human readable (handle string values from API)
    try:
        rx_rate = float(port_data.get('rx_rate_bps', 0))
        tx_rate = float(port_data.get('tx_rate_bps', 0))
    except (ValueError, TypeError):
        rx_rate = 0
        tx_rate = 0
        
    port_data['rx_mbps'] = round(rx_rate / 1000000, 2)
    port_data['tx_mbps'] = round(tx_rate / 1000000, 2)
    
    return jsonify(port_data)

@ops_center_bp.route('/api/switch/port/<int:port_id>/toggle', methods=['POST'])
def api_switch_port_toggle(port_id):
    """
    Toggle a switch port on/off.
    
    Args:
        port_id: Port number (1-48)
        
    Returns:
        JSON response with success status
    """
    mikrotik = MikroTikAPI()
    
    # Get current state
    port_data = mikrotik.get_port_details(port_id)
    if not port_data:
        return jsonify({'error': 'Port not found'}), 404
    
    # Toggle the state
    new_state = not port_data['enabled']
    success = mikrotik.toggle_port(port_id, new_state)
    
    return jsonify({
        'success': success,
        'port_id': port_id,
        'new_state': 'enabled' if new_state else 'disabled'
    })

@ops_center_bp.route('/api/switch/port/<int:port_id>/name', methods=['POST'])
def api_switch_port_rename(port_id):
    """
    Update port name/description.
    
    Args:
        port_id: Port number (1-48)
        
    Request JSON:
        name: New port name
        
    Returns:
        JSON response with success status
    """
    from flask import request
    
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Name required'}), 400
    
    mikrotik = MikroTikAPI()
    success = mikrotik.set_port_name(port_id, data['name'])
    
    return jsonify({
        'success': success,
        'port_id': port_id,
        'new_name': data['name']
    })