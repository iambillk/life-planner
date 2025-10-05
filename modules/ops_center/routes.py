"""
Operations Command Center - Routes
Version: 1.2.0
Last Modified: 2025-01-XX
Author: Billas
Description: All routes for Operations Command Center module

File: /modules/ops_center/routes.py

CHANGELOG:
- 1.2.0 (2025-01-XX): Added DLI PDU integration replacing mock PDU data
                      Added PDU control endpoints for outlet management
- 1.1.0 (2024-01-XX): Added MikroTik switch integration
- 1.0.0 (2024-01-XX): Initial implementation with mock data
"""

from flask import Blueprint, render_template, jsonify, request, current_app
from datetime import datetime
import random
from modules.ops_center.integrations import OpsLibreNMS
from modules.ops_center.mikrotik import MikroTikAPI
from modules.ops_center.dli_pdu import DLIPduAPI  # NEW IMPORT for DLI PDU

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
    
    # Initialize MikroTik integration
    mikrotik = MikroTikAPI()
    
    # Initialize DLI PDU integration - NEW
    dli_pdu = DLIPduAPI()
    
    # Get real LibreNMS data
    device_stats = libre.get_device_stats()
    wan_stats = libre.get_port_bandwidth()
    alert_summary = libre.get_alert_summary()
    graph_urls = libre.get_port_graphs()
    ips_alerts = libre.get_ips_alerts()
    
    # Get MikroTik switch data
    switch_ports = mikrotik.get_all_ports()
    
    # Calculate switch statistics
    switch_stats = {
        'total_ports': len(switch_ports),
        'ports_up': sum(1 for p in switch_ports if p['status'] == 'up'),
        'ports_down': sum(1 for p in switch_ports if p['status'] == 'down'),
        'ports_errors': sum(1 for p in switch_ports if p.get('has_errors', False))
    }
    
    # Get REAL DLI PDU data - REPLACED MOCK DATA
    pdu_outlets = dli_pdu.get_all_outlets()
    pdu_power = dli_pdu.get_power_status()
    
    # Build PDU context with real data
    pdu_context = {
        'name': current_app.config.get('DLI_PDU_NAME', 'DLI-PDU-1'),
        'current_amps': pdu_power['current_amps'] if pdu_power else 0.0,
        'max_amps': pdu_power['max_amps'] if pdu_power else 15,
        'voltage': pdu_power['voltage'] if pdu_power else 120,
        'watts': pdu_power['watts'] if pdu_power else 0.0,
        'outlets': [
            {
                'id': outlet['number'],  # Human-friendly 1-8
                'outlet_id': outlet['id'],  # API ID 0-7
                'on': outlet['physical_state'],
                'name': outlet['name'],
                'locked': outlet['locked']
            }
            for outlet in pdu_outlets
        ] if pdu_outlets else []
    }
    
    # Build context with mix of real and mock data
    context = {
        'page_title': 'Operations Command Center',
        'last_refresh': datetime.now().strftime('%H:%M:%S'),
        'system_status': device_stats['status'],
        
        # WAN data with REAL bandwidth
        'wan1': wan_stats['wan1'],
        'wan2': wan_stats['wan2'],
        
        # Graph URLs for embedding
        'wan1_graph_url': graph_urls['wan1_graph'],
        'wan2_graph_url': graph_urls['wan2_graph'],
        
        # Alerts with REAL IPS DATA
        'alerts': {
            'ips_count': ips_alerts['count'],
            'ips_latest': ips_alerts['latest'],
            'firewalla_count': 1,  # Still mock
            'firewalla_latest': 'Port Scan',  # Still mock
            'syslogs_count': alert_summary['warning'],
            'hostmon_downtime': '4min @3am'  # Still mock
        },
        
        # PDU with REAL DLI DATA - NO MORE MOCK!
        'pdu': pdu_context,
        
        # Switch display - keeping for backwards compatibility
        'switches': [
            {'name': 'MikroTik', 'ports': 24, 'active': 18},
            {'name': 'Zyxel-1', 'ports': 48, 'active': 42},
            {'name': 'Zyxel-2', 'ports': 24, 'active': 20}
        ],
        
        # MikroTik switch data for grid display
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
    
    Version: 1.1.0
    Updated: 2025-01-XX - Added real DLI PDU data
    
    Returns:
        JSON response with updated metrics
    """
    # Get real LibreNMS data for refresh
    libre = OpsLibreNMS()
    alert_summary = libre.get_alert_summary()
    wan_stats = libre.get_port_bandwidth()
    ips_alerts = libre.get_ips_alerts()
    
    # Get MikroTik data for refresh
    mikrotik = MikroTikAPI()
    switch_ports = mikrotik.get_all_ports()
    switch_stats = {
        'ports_up': sum(1 for p in switch_ports if p['status'] == 'up'),
        'total_ports': len(switch_ports)
    }
    
    # Get DLI PDU data for refresh - NEW
    dli_pdu = DLIPduAPI()
    pdu_power = dli_pdu.get_power_status()
    
    # Return real data
    return jsonify({
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'wan1_down': wan_stats['wan1']['download_mbps'],
        'wan1_up': wan_stats['wan1']['upload_mbps'],
        'wan2_down': wan_stats['wan2']['download_mbps'],
        'wan2_up': wan_stats['wan2']['upload_mbps'],
        'ips_count': ips_alerts['count'],
        'pdu_amps': pdu_power['current_amps'] if pdu_power else 0.0,  # REAL PDU AMPS!
        'switch_ports_up': switch_stats['ports_up'],
        'switch_total_ports': switch_stats['total_ports']
    })

# ============== NEW DLI PDU Control Endpoints ==============

@ops_center_bp.route('/api/pdu/outlet/<int:outlet_id>/toggle', methods=['POST'])
def api_pdu_outlet_toggle(outlet_id):
    """
    Toggle PDU outlet state (on/off).
    
    Version: 1.0.0
    Added: 2025-01-XX
    
    Args:
        outlet_id: Outlet number (1-8 human-friendly)
        
    Returns:
        JSON response with success status
    """
    try:
        # Convert human-friendly ID to API ID (1-8 to 0-7)
        api_outlet_id = outlet_id - 1
        
        # Initialize DLI PDU
        dli_pdu = DLIPduAPI()
        
        # Get current state
        outlet = dli_pdu.get_outlet_status(api_outlet_id)
        if not outlet:
            return jsonify({'success': False, 'error': 'Outlet not found'}), 404
        
        # Check if outlet is locked
        if outlet.get('locked', False):
            return jsonify({'success': False, 'error': 'Outlet is locked'}), 403
        
        # Toggle the state
        new_state = not outlet['physical_state']
        success = dli_pdu.set_outlet_state(api_outlet_id, new_state)
        
        if success:
            return jsonify({
                'success': True,
                'outlet_id': outlet_id,
                'new_state': 'on' if new_state else 'off'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to toggle outlet'}), 500
            
    except Exception as e:
        print(f"[PDU] Error toggling outlet {outlet_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ops_center_bp.route('/api/pdu/outlet/<int:outlet_id>/cycle', methods=['POST'])
def api_pdu_outlet_cycle(outlet_id):
    """
    Cycle PDU outlet (power off, wait, power on).
    
    Version: 1.0.0
    Added: 2025-01-XX
    
    Args:
        outlet_id: Outlet number (1-8 human-friendly)
        
    Returns:
        JSON response with success status
    """
    try:
        # Convert human-friendly ID to API ID
        api_outlet_id = outlet_id - 1
        
        # Get optional delay parameter
        delay = request.json.get('delay', None) if request.is_json else None
        
        # Initialize DLI PDU
        dli_pdu = DLIPduAPI()
        
        # Check if outlet is locked
        outlet = dli_pdu.get_outlet_status(api_outlet_id)
        if outlet and outlet.get('locked', False):
            return jsonify({'success': False, 'error': 'Outlet is locked'}), 403
        
        # Cycle the outlet
        success = dli_pdu.cycle_outlet(api_outlet_id, delay)
        
        if success:
            return jsonify({
                'success': True,
                'outlet_id': outlet_id,
                'message': f'Outlet {outlet_id} cycling...'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to cycle outlet'}), 500
            
    except Exception as e:
        print(f"[PDU] Error cycling outlet {outlet_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ops_center_bp.route('/api/pdu/outlets/all', methods=['GET'])
def api_pdu_outlets_all():
    """
    Get status of all PDU outlets.
    
    Version: 1.0.0
    Added: 2025-01-XX
    
    Returns:
        JSON response with all outlet statuses
    """
    try:
        dli_pdu = DLIPduAPI()
        outlets = dli_pdu.get_all_outlets()
        power_status = dli_pdu.get_power_status()
        
        return jsonify({
            'success': True,
            'outlets': [
                {
                    'id': o['number'],
                    'name': o['name'],
                    'state': o['physical_state'],
                    'locked': o['locked']
                }
                for o in outlets
            ],
            'power': {
                'current_amps': power_status['current_amps'],
                'max_amps': power_status['max_amps'],
                'voltage': power_status['voltage'],
                'watts': power_status['watts']
            } if power_status else None
        })
    except Exception as e:
        print(f"[PDU] Error getting outlet status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ops_center_bp.route('/api/pdu/outlet/<int:outlet_id>/name', methods=['POST'])
def api_pdu_outlet_rename(outlet_id):
    """
    Rename a PDU outlet.
    
    Version: 1.0.0
    Added: 2025-01-XX
    
    Args:
        outlet_id: Outlet number (1-8 human-friendly)
        
    Returns:
        JSON response with success status
    """
    try:
        # Get new name from request
        new_name = request.json.get('name', '') if request.is_json else ''
        if not new_name:
            return jsonify({'success': False, 'error': 'Name required'}), 400
        
        # Convert human-friendly ID to API ID
        api_outlet_id = outlet_id - 1
        
        # Initialize DLI PDU
        dli_pdu = DLIPduAPI()
        
        # Set the new name
        success = dli_pdu.set_outlet_name(api_outlet_id, new_name)
        
        if success:
            return jsonify({
                'success': True,
                'outlet_id': outlet_id,
                'new_name': new_name
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to rename outlet'}), 500
            
    except Exception as e:
        print(f"[PDU] Error renaming outlet {outlet_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Continue with existing routes...
@ops_center_bp.route('/api/ips-details')
def api_ips_details():
    """
    Get detailed IPS alerts with analytics for modal display.
    [Rest of existing code continues...]
    """
    # [Keep existing implementation]
    pass