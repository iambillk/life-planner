# modules/admin_tools/constants.py
"""
Admin Tools Constants
Tool configurations, categories, and default settings
Version: 1.1.0 (Added Port Scanner)
Created: 2025-01-08
Updated: 2025-10-09
"""

# Tool Categories for organization
TOOL_CATEGORIES = {
    'network': {
        'name': 'Network Diagnostics',
        'icon': '🌐',
        'tools': ['ping', 'traceroute', 'pathping', 'nslookup', 'ipconfig']
    },
    'whois': {
        'name': 'WHOIS Lookups',
        'icon': '🔍',
        'tools': ['whois_domain', 'whois_ip']
    },
    'dns': {
        'name': 'DNS Tools',
        'icon': '🗂️',
        'tools': ['nslookup', 'dig', 'dns_health']
    },
    'connectivity': {
        'name': 'Connectivity Tests',
        'icon': '📡',
        'tools': ['telnet', 'ssh_test', 'http_test']
    },
    'system': {
        'name': 'System Info',
        'icon': '💻',
        'tools': ['netstat', 'arp', 'route']
    },
    'security': {
        'name': 'Security Tools',
        'icon': '🔒',
        'tools': ['port_scan']
    }
}

# Tool Definitions
# Each tool has: name, command, description, exe_path (if custom), accepts_target
TOOLS = {
    'ping': {
        'name': 'Ping',
        'description': 'Test connectivity to a host',
        'category': 'network',
        'icon': '📶',
        'command': 'ping',
        'is_windows_builtin': True,
        'accepts_target': True,
        'target_label': 'IP or Hostname',
        'parameters': [
            {'name': 'count', 'label': 'Count (-n)', 'type': 'number', 'default': 4},
            {'name': 'size', 'label': 'Packet Size (-l)', 'type': 'number', 'default': 32},
            {'name': 'timeout', 'label': 'Timeout (-w)', 'type': 'number', 'default': 1000}
        ],
        'output_parser': 'parse_ping'
    },
    
    'traceroute': {
        'name': 'Traceroute',
        'description': 'Trace the route packets take to a destination',
        'category': 'network',
        'icon': '🛤️',
        'command': 'tracert',  # Windows uses tracert
        'is_windows_builtin': True,
        'accepts_target': True,
        'target_label': 'IP or Hostname',
        'parameters': [
            {'name': 'max_hops', 'label': 'Max Hops (-h)', 'type': 'number', 'default': 30}
        ],
        'output_parser': 'parse_traceroute'
    },
    
    'pathping': {
        'name': 'PathPing',
        'description': 'Combines ping and traceroute with network statistics',
        'category': 'network',
        'icon': '📊',
        'command': 'pathping',
        'is_windows_builtin': True,
        'accepts_target': True,
        'target_label': 'IP or Hostname',
        'parameters': [
            {'name': 'queries', 'label': 'Queries per Hop (-q)', 'type': 'number', 'default': 100}
        ],
        'output_parser': None
    },
    
    'nslookup': {
        'name': 'NSLookup',
        'description': 'DNS lookup to resolve hostnames',
        'category': 'dns',
        'icon': '🔎',
        'command': 'nslookup',
        'is_windows_builtin': True,
        'accepts_target': True,
        'target_label': 'Domain or IP',
        'parameters': [],
        'output_parser': 'parse_nslookup'
    },
    
    'whois_domain': {
        'name': 'WHOIS Domain',
        'description': 'Domain registration information',
        'category': 'whois',
        'icon': '🌍',
        'command': None,  # Will use custom .exe
        'exe_path': 'whois_domain.exe',  # User's custom tool
        'is_windows_builtin': False,
        'accepts_target': True,
        'target_label': 'Domain Name',
        'parameters': [],
        'output_parser': None
    },
    
    'whois_ip': {
        'name': 'WHOIS IP',
        'description': 'IP address ownership information',
        'category': 'whois',
        'icon': '🔢',
        'command': None,
        'exe_path': 'whois_ip.exe',  # User's custom tool
        'is_windows_builtin': False,
        'accepts_target': True,
        'target_label': 'IP Address',
        'parameters': [],
        'output_parser': None
    },
    
    'ipconfig': {
        'name': 'IPConfig',
        'description': 'Display network adapter configuration',
        'category': 'system',
        'icon': '🖥️',
        'command': 'ipconfig',
        'is_windows_builtin': True,
        'accepts_target': False,
        'parameters': [
            {'name': 'all', 'label': 'Show All (/all)', 'type': 'checkbox', 'default': True}
        ],
        'output_parser': None
    },
    
    'netstat': {
        'name': 'Netstat',
        'description': 'Display network connections and statistics',
        'category': 'system',
        'icon': '📈',
        'command': 'netstat',
        'is_windows_builtin': True,
        'accepts_target': False,
        'parameters': [
            {'name': 'all', 'label': 'All Connections (-a)', 'type': 'checkbox', 'default': True},
            {'name': 'numeric', 'label': 'Numeric (-n)', 'type': 'checkbox', 'default': True}
        ],
        'output_parser': None
    },

    'dns_health': {
        'name': 'DNS Health Check',
        'description': 'Comprehensive DNS analysis and validation',
        'category': 'dns',
        'icon': '🏥',
        'command': None,
        'is_windows_builtin': False,
        'accepts_target': True,
        'target_label': 'Domain Name',
        'parameters': [],
        'output_parser': 'parse_dns_health'
    },
    
    'arp': {
        'name': 'ARP Table',
        'description': 'Display ARP cache (IP to MAC mappings)',
        'category': 'system',
        'icon': '📇',
        'command': 'arp',
        'is_windows_builtin': True,
        'accepts_target': False,
        'parameters': [
            {'name': 'all', 'label': 'Show All (-a)', 'type': 'checkbox', 'default': True}
        ],
        'output_parser': None
    },
    
    'port_scan': {
        'name': 'Port Scanner',
        'description': 'Scan ports using Nmap to discover open services',
        'category': 'security',
        'icon': '🔍',
        'command': None,  # Handled specially
        'is_windows_builtin': False,
        'accepts_target': True,
        'target_label': 'IP Address or Hostname',
        'parameters': [
            {
                'name': 'scan_type',
                'label': 'Scan Type',
                'type': 'select',
                'options': [
                    {'value': 'quick', 'label': 'Quick Scan (Top 100 ports, ~10-20s)'},
                    {'value': 'standard', 'label': 'Standard Scan (Top 1000 ports + versions, ~1-2min)'},
                    {'value': 'thorough', 'label': 'Thorough Scan (Top 1000 + OS detection, ~2-5min)'},
                    {'value': 'custom', 'label': 'Custom Ports (specify below)'}
                ],
                'default': 'quick'
            },
            {
                'name': 'custom_ports',
                'label': 'Custom Ports (comma-separated)',
                'type': 'text',
                'placeholder': 'e.g., 22,80,443,3389',
                'default': '',
                'depends_on': {'scan_type': 'custom'}
            }
        ],
        'output_parser': 'parse_nmap',
        'warning': '⚠️ Only scan systems you are authorized to test. Unauthorized scanning may be illegal.',
        'requires_admin': False,
        'admin_note': 'OS detection requires administrator/root privileges'
    },

    'http_test': {
        'name': 'HTTP/HTTPS Test',
        'description': 'Test website connectivity, SSL certificates, and hosting information',
        'category': 'connectivity',
        'icon': '🌐',
        'command': None,
        'is_windows_builtin': False,
        'accepts_target': True,
        'target_label': 'Website URL (e.g., example.com or https://example.com)',
        'parameters': [
            {
                'name': 'follow_redirects',
                'label': 'Follow Redirects',
                'type': 'checkbox',
                'default': True
            },
            {
                'name': 'timeout',
                'label': 'Timeout (seconds)',
                'type': 'number',
                'default': 10
            },
        ],
        'output_parser': None,
        'requires_admin': False
    }
}

# Nmap Scan Preset Configurations
NMAP_SCAN_PRESETS = {
    'quick': {
        'name': 'Quick Scan',
        'description': 'Top 100 most common ports',
        'flags': ['-Pn', '--top-ports', '100', '-T4'],
        'estimated_time': '10-20 seconds',
        'requires_admin': False
    },
    'standard': {
        'name': 'Standard Scan',
        'description': 'Top 1000 ports with service version detection',
        'flags': ['-Pn', '-sV', '--top-ports', '1000', '-T4'],
        'estimated_time': '1-2 minutes',
        'requires_admin': False
    },
    'thorough': {
        'name': 'Thorough Scan',
        'description': 'Top 1000 ports with service versions and OS detection',
        'flags': ['-Pn', '-sV', '-O', '--top-ports', '1000', '-T4'],
        'estimated_time': '2-5 minutes',
        'requires_admin': True,
        'admin_warning': 'OS detection works best with administrator/root privileges'
    },
    'custom': {
        'name': 'Custom Ports',
        'description': 'User-specified port list',
        'flags': ['-Pn', '-sV', '-T4'],  # -p flag added dynamically
        'estimated_time': 'Variable',
        'requires_admin': False
    }
}

# Knowledge Base Item Types
CONTENT_TYPES = {
    'text': {
        'name': 'Text/Code',
        'icon': '📝',
        'description': 'Paste text content directly',
        'accepts_files': False
    },
    'file': {
        'name': 'File Upload',
        'icon': '📎',
        'description': 'Upload a file',
        'accepts_files': True
    },
    'url': {
        'name': 'External Link',
        'icon': '🔗',
        'description': 'Link to external resource',
        'accepts_files': False
    }
}

# Allowed file extensions for knowledge base uploads
ALLOWED_EXTENSIONS = {
    # Configs
    'cfg', 'conf', 'config', 'ini', 'yaml', 'yml', 'json', 'xml',
    # Scripts
    'ps1', 'bat', 'cmd', 'sh', 'bash', 'py', 'js',
    # Text/Docs
    'txt', 'md', 'log', 'csv',
    # Images (for diagrams, screenshots)
    'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp',
    # Archives (for backup bundles)
    'zip', '7z', 'tar', 'gz',
    # PDFs
    'pdf',
    # Office docs
    'doc', 'docx', 'xls', 'xlsx',
    # ISOs
    'iso'
}

# File size limits (in bytes)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Default tool paths (user can override in settings)
DEFAULT_TOOL_PATHS = {
    'custom_tools_dir': 'C:\\Tools',  # Where user's .exe files live
    'whois_domain': 'C:\\Tools\\whois_domain.exe',
    'whois_ip': 'C:\\Tools\\whois_ip.exe',
    'nmap': 'C:\\Program Files (x86)\\Nmap\\nmap.exe',
}

# Predefined tags for quick tagging
SUGGESTED_TAGS = [
    'production', 'development', 'backup', 'emergency', 'work', 'homelab',
    'cisco', 'dell', 'hp', 'mikrotik', 'ubiquiti', 'pfsense', 'proxmox',
    'network', 'server', 'storage', 'firewall', 'switch', 'router',
    'windows', 'linux', 'docker', 'vm', 'critical', 'archived'
]

# Quick action templates for common documentation
DOC_TEMPLATES = {
    'switch_backup': {
        'title_template': 'Switch Backup - {device_name} - {date}',
        'category': 'Configs & Backups',
        'suggested_tags': ['backup', 'switch', 'network'],
        'content_template': '''# Switch Configuration Backup
Device: {device_name}
IP: {ip_address}
Date: {date}
Backup Type: {backup_type}

---
Configuration:
{config_content}
'''
    },
    
    'network_diagram': {
        'title_template': 'Network Diagram - {location} - {date}',
        'category': 'Network Documentation',
        'suggested_tags': ['network', 'diagram', 'documentation'],
        'content_template': '''# Network Diagram
Location: {location}
Date: {date}
Notes:
{notes}
'''
    },
    
    'ip_schema': {
        'title_template': 'IP Address Schema - {network_name}',
        'category': 'Network Documentation',
        'suggested_tags': ['network', 'ip-schema', 'documentation'],
        'content_template': '''# IP Address Schema
Network: {network_name}
Subnet: {subnet}
Gateway: {gateway}

Reserved Ranges:
- {range1}
- {range2}

Notes:
{notes}
'''
    },
    
    'incident_log': {
        'title_template': 'Incident Log - {date} - {summary}',
        'category': 'Logs',
        'suggested_tags': ['incident', 'troubleshooting'],
        'content_template': '''# Incident Log
Date: {date}
Summary: {summary}
Severity: {severity}

## Problem
{problem_description}

## Actions Taken
{actions}

## Resolution
{resolution}

## Follow-up
{followup}
'''
    },
    
    'cheat_sheet': {
        'title_template': 'Cheat Sheet - {topic}',
        'category': 'Cheat Sheets',
        'suggested_tags': ['cheatsheet', 'reference'],
        'content_template': '''# {topic} Cheat Sheet

## Common Commands
{commands}

## Tips & Tricks
{tips}

## References
{references}
'''
    }
}

# Color palette for tags
TAG_COLORS = [
    '#6ea8ff',  # Blue (default)
    '#22c55e',  # Green
    '#f59e0b',  # Orange
    '#ef4444',  # Red
    '#8b5cf6',  # Purple
    '#06b6d4',  # Cyan
    '#ec4899',  # Pink
    '#f97316',  # Deep Orange
]

# Quick filters for tool history
HISTORY_FILTERS = {
    'today': {'days': 1, 'label': 'Today'},
    'week': {'days': 7, 'label': 'This Week'},
    'month': {'days': 30, 'label': 'This Month'},
    'all': {'days': None, 'label': 'All Time'}
}

# Your Network Configuration for Hosting Detection
YOUR_NETWORK_CONFIG = {
    'company_name': 'TotalChoice Hosting',
    'ip_ranges': [],
    'server_names': {}
}