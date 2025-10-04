"""
Operations Command Center - Routes
Version: 1.0.0
Last Modified: 2024-01-XX
Author: Billas
Description: All routes for Operations Command Center module

File: /modules/ops_center/routes.py

CHANGELOG:
- 1.0.0 (2024-01-XX): Initial implementation with mock data
"""

from flask import Blueprint, render_template, jsonify
from datetime import datetime
import random
from modules.ops_center.integrations import OpsLibreNMS

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
    
    # Get real LibreNMS data
    device_stats = libre.get_device_stats()
    wan_stats = libre.get_port_bandwidth()
    alert_summary = libre.get_alert_summary()
    graph_urls = libre.get_port_graphs()
    ips_alerts = libre.get_ips_alerts()  # NEW - get real IPS alerts
    
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
        
        # Rest stays the same...
        'pdu': {
            'name': 'PDU-1',
            'current_amps': 8.2,
            'max_amps': 15,
            'outlets': [
                {'id': i, 'on': i != 3, 'name': f'Outlet-{i}'} 
                for i in range(1, 11)
            ]
        },
        
        'switches': [
            {'name': 'MikroTik', 'ports': 24, 'active': 18},
            {'name': 'Zyxel-1', 'ports': 48, 'active': 42},
            {'name': 'Zyxel-2', 'ports': 24, 'active': 20}
        ],
        
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
    ips_alerts = libre.get_ips_alerts()  # NEW - get real IPS data
    
    # Return real data
    return jsonify({
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'wan1_down': wan_stats['wan1']['download_mbps'],
        'wan1_up': wan_stats['wan1']['upload_mbps'],
        'wan2_down': wan_stats['wan2']['download_mbps'],
        'wan2_up': wan_stats['wan2']['upload_mbps'],
        'ips_count': ips_alerts['count'],  # REAL IPS count
        'pdu_amps': round(random.uniform(7.5, 9.5), 1)  # Still mock
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