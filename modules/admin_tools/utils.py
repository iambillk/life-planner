# modules/admin_tools/utils.py
"""
Admin Tools Utilities
Helper functions for tool execution, file handling, and parsing

Version: 2.1.0  (Awesome DNS Health Check)
Updated: 2025-10-08

Highlights in 2.1.0:
- IntoDNS-style docs per check: explain/why/fix/refs/evidence
- Top-10 robustness checks added:
  * Parent/child glue IP consistency
  * TCP/53 support per NS
  * EDNS compliance
  * Stealth/Lame NS detection
  * NS IP sanity (no RFC1918/bogon)
  * CAA presence
  * SPF single-record & lookup-count limit (<=10)
  * DMARC depth (policy, alignment, rua)
  * SMTP STARTTLS probe on MX (banner + TLS handshake)
  * Apex CNAME (illegal) + Dangling CNAME detection

Notes:
- Minimal changes to your public API (execute_tool, parse_*, etc.).
- All new explanations are attached automatically to checks.
"""

import os
import subprocess
import json
import time
import socket
import ipaddress
import ssl
from datetime import datetime

import dns.resolver
import dns.query
import dns.zone
import dns.reversename
from dns.exception import DNSException

from werkzeug.utils import secure_filename
from flask import current_app

from .constants import TOOLS, ALLOWED_EXTENSIONS, MAX_FILE_SIZE, DEFAULT_TOOL_PATHS


# ==================== FILE HANDLING ====================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_size(file_storage):
    """Get size of uploaded file"""
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    return size


def save_knowledge_file(file_storage, category_name='misc'):
    """
    Save uploaded file to knowledge base directory
    Returns: (filename, relative_path, file_size, mime_type)
    """
    if not file_storage or not allowed_file(file_storage.filename):
        return None, None, None, None

    # Check file size
    file_size = get_file_size(file_storage)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Max size: {MAX_FILE_SIZE / (1024*1024)}MB")

    # Create safe filename with timestamp
    original_filename = secure_filename(file_storage.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{original_filename}"

    # Create category subdirectory
    upload_base = os.path.join(current_app.config['UPLOAD_FOLDER'], 'admin_tools', 'knowledge_base')
    category_dir = os.path.join(upload_base, secure_filename(category_name))
    os.makedirs(category_dir, exist_ok=True)

    # Save file
    filepath = os.path.join(category_dir, filename)
    file_storage.save(filepath)

    # Get MIME type
    mime_type = file_storage.content_type or 'application/octet-stream'

    # Return relative path from upload folder
    relative_path = os.path.join('admin_tools', 'knowledge_base', secure_filename(category_name), filename)
    return filename, relative_path, file_size, mime_type


def format_file_size(bytes_size):
    """Format bytes to human-readable size"""
    if bytes_size is None:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def get_file_icon(filename):
    """Get appropriate icon emoji for file type"""
    if not filename:
        return '📄'
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    icon_map = {
        'cfg': '⚙️', 'conf': '⚙️', 'config': '⚙️', 'ini': '⚙️',
        'yaml': '📋', 'yml': '📋', 'json': '📋', 'xml': '📋',
        'ps1': '💻', 'bat': '💻', 'cmd': '💻', 'sh': '🐧', 'bash': '🐧',
        'py': '🐍', 'js': '📜',
        'log': '📊', 'txt': '📝',
        'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'svg': '🎨',
        'zip': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'iso': '💿',
        'pdf': '📕', 'doc': '📘', 'docx': '📘',
        'csv': '📊', 'xls': '📊', 'xlsx': '📊',
    }
    return icon_map.get(ext, '📄')


def sanitize_filename(filename):
    """Remove unsafe characters from filename"""
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        filename = filename.replace(char, '_')
    return filename


def get_mime_icon(mime_type):
    """Get icon based on MIME type"""
    if not mime_type:
        return '📄'
    if mime_type.startswith('text/'):
        return '📝'
    if mime_type.startswith('image/'):
        return '🖼️'
    if mime_type.startswith('application/'):
        if 'pdf' in mime_type:
            return '📕'
        if 'zip' in mime_type or 'compressed' in mime_type:
            return '📦'
        if 'json' in mime_type or 'xml' in mime_type:
            return '📋'
    return '📄'


# ==================== TOOL CONFIGURATION ====================

def get_tool_config(tool_name):
    """Get configuration for a specific tool"""
    return TOOLS.get(tool_name)


def build_tool_command(tool_name, target=None, parameters=None):
    """
    Build command line arguments for a tool
    Returns: (command_list, command_string)
    """
    tool_config = get_tool_config(tool_name)
    if not tool_config:
        raise ValueError(f"Unknown tool: {tool_name}")

    parameters = parameters or {}

    # Start with base command
    if tool_config['is_windows_builtin']:
        cmd = [tool_config['command']]
    else:
        exe_path = parameters.get('exe_path') or \
                   DEFAULT_TOOL_PATHS.get(tool_name) or \
                   tool_config.get('exe_path')
        if not exe_path or not os.path.exists(exe_path):
            raise FileNotFoundError(f"Tool executable not found: {exe_path}")
        cmd = [exe_path]

    # Add tool-specific parameters
    if tool_name == 'ping':
        cmd.extend(['-n', str(parameters.get('count', 4))])
        if parameters.get('size'):
            cmd.extend(['-l', str(parameters['size'])])
        if parameters.get('timeout'):
            cmd.extend(['-w', str(parameters['timeout'])])

    elif tool_name == 'traceroute':
        if parameters.get('max_hops'):
            cmd.extend(['-h', str(parameters['max_hops'])])

    elif tool_name == 'pathping':
        if parameters.get('queries'):
            cmd.extend(['-q', str(parameters['queries'])])

    elif tool_name == 'ipconfig':
        if parameters.get('all', True):
            cmd.append('/all')

    elif tool_name == 'netstat':
        if parameters.get('all', True):
            cmd.append('-a')
        if parameters.get('numeric', True):
            cmd.append('-n')

    elif tool_name == 'arp':
        if parameters.get('all', True):
            cmd.append('-a')

    # Add target if tool accepts it
    if target and tool_config['accepts_target']:
        cmd.append(target)

    command_string = ' '.join(cmd)
    return cmd, command_string


# ==================== DNS DOCS (IntoDNS-style, extended) ====================

CHECK_DOCS = {
    # ---- Parent / Delegation ----
    "Parent Zone::Parent NS Records": {
        "explain": "Query the parent zone (registry) to list the nameservers delegated for this domain.",
        "why": "Resolvers start at the parent; if delegation is wrong, the domain may fail to resolve or be unreliable.",
        "fix": "Update nameserver delegation at your registrar to the correct authoritative NS set.",
        "refs": ["RFC 1034 §4.2", "RFC 1035 §3.3.11"]
    },
    "Parent Zone::Parent/Child Match": {
        "explain": "Compare the NS set at the parent (delegation) with the NS set inside the child zone.",
        "why": "Mismatch causes intermittent failures: resolvers may query servers the child zone doesn’t list (or vice versa).",
        "fix": "Make the NS set identical in both parent delegation and the child zone.",
        "refs": ["RFC 1034 §4.2", "RFC 1912 §2.3"]
    },

    # ---- Nameservers ----
    "Nameservers::NS Count": {
        "explain": "Count how many authoritative nameservers the zone publishes.",
        "why": "Too few nameservers is a single point of failure; best practice is two or more on diverse networks.",
        "fix": "Configure at least two authoritative nameservers on separate networks and update delegation.",
        "refs": ["RFC 2182 (Selection and Operation of Secondary DNS Servers)"]
    },
    "Nameservers::NS Host": {
        "explain": "Resolve each listed nameserver hostname to its IP address(es).",
        "why": "If a nameserver hostname doesn’t resolve, the parent points to a dead end and resolution fails.",
        "fix": "Ensure each NS hostname has working A/AAAA records reachable from the Internet.",
        "refs": ["RFC 1035 §3.3.11"]
    },
    "Nameservers::Glue Records": {
        "explain": "Identify in-bailiwick nameservers that require glue at the parent.",
        "why": "Without glue, resolvers can get stuck trying to find the NS IPs, causing resolution loops.",
        "fix": "Add/update glue A/AAAA at the registrar for in-bailiwick nameservers.",
        "refs": ["RFC 1034 §4.2.1"]
    },
    "Nameservers::Glue Consistency": {
        "explain": "Compare parent glue A/AAAA with child zone A/AAAA for in-bailiwick NS.",
        "why": "Stale glue sends resolvers to the wrong server; outages and poisoning risks follow.",
        "fix": "Update glue at registrar whenever NS IPs change; keep child NS records in sync.",
        "refs": ["RFC 1034 §4.2.1"]
    },
    "Nameservers::Network Diversity": {
        "explain": "Check whether nameservers sit on diverse networks (ASN) rather than a single provider.",
        "why": "Provider or network outages can take all nameservers down if they share the same upstream.",
        "fix": "Host secondaries with different providers/ASNs; consider geographic diversity.",
        "refs": ["RFC 2182"]
    },
    "Nameservers::NS IP Sanity": {
        "explain": "Ensure NS IPs are public, routable addresses (not private, loopback, link-local, or bogons).",
        "why": "Public resolvers can’t reach private/bogon IPs; delegation becomes unusable.",
        "fix": "Assign globally routable IPs to authoritative NS and update glue/records accordingly.",
        "refs": ["RFC 6890"]
    },

    # ---- Performance / Robustness ----
    "Performance::NS Response": {
        "explain": "Measure per-nameserver SOA query latency.",
        "why": "Slow or timing-out nameservers degrade user experience and may trigger resolver failovers.",
        "fix": "Tune DNS software, remove overloaded servers, distribute globally, or add capacity.",
        "refs": ["Operational best practices"]
    },

    # ---- Security / Protocol Features ----
    "Security::Recursion": {
        "explain": "Check whether an authoritative nameserver performs open recursion for arbitrary clients.",
        "why": "Open resolvers are abused in DDoS amplification and can leak internal data.",
        "fix": "Disable recursion on authoritative servers or restrict it to trusted IPs only.",
        "refs": ["BCP 140 (DNS OpSec)", "US-CERT TA13-088A"]
    },
    "Security::TCP 53": {
        "explain": "Attempt DNS queries over TCP/53 to each authoritative nameserver.",
        "why": "DNSSEC and large responses require TCP; blocking it breaks standards-compliant resolution.",
        "fix": "Permit TCP/53 at firewalls and ensure the DNS daemon listens on TCP as well as UDP.",
        "refs": ["RFC 7766 (DNS over TCP)"]
    },
    "Security::EDNS": {
        "explain": "Send EDNS0 queries with a safe UDP payload size and inspect server behavior.",
        "why": "Without EDNS, responses may truncate/fail (especially with DNSSEC), causing flakiness.",
        "fix": "Upgrade or reconfigure DNS servers/load-balancers to properly support EDNS.",
        "refs": ["RFC 6891 (EDNS0)"]
    },
    "Security::Stealth/Lame NS": {
        "explain": "Detect NS that are listed but not authoritative (lame) and servers that answer AA but aren’t listed (stealth).",
        "why": "Lame NS degrade reliability; stealth NS indicate misconfiguration and surprise failure modes.",
        "fix": "Remove lame servers from parent/child; add intended authoritative servers to both NS sets.",
        "refs": ["RFC 1912 §2.8"]
    },
    "Security::Authority Pass": {
        "explain": "Confirm the server replies authoritatively (AA=1) for the zone.",
        "why": "Non-authoritative answers from listed NS suggest lame delegation or proxying.",
        "fix": "Serve the zone on these NS with AA responses or remove them from the NS set.",
        "refs": ["RFC 1035 §4.1.1"]
    },
    "Security::Zone XFR": {
        "explain": "Attempt an AXFR (full zone transfer) from each nameserver.",
        "why": "Unrestricted zone transfers leak your entire zone to anyone on the Internet.",
        "fix": "Restrict AXFR to specific secondary IPs or disable it.",
        "refs": ["RFC 5936 (AXFR)"]
    },
    "Security::Blacklist": {
        "explain": "Check selected DNSBLs for the site’s A record IP (informational).",
        "why": "Listed web IPs can reflect compromised hosts or poor neighbor reputation.",
        "fix": "Investigate why the IP is listed; remediate and request delisting if appropriate.",
        "refs": ["Provider DNSBL documentation"]
    },

    # ---- SOA / Zone Timers ----
    "SOA::SOA Record": {
        "explain": "Fetch the zone’s SOA record and display primary MNAME, RNAME, serial and timers.",
        "why": "SOA defines replication behavior; wrong values cause slow or broken zone propagation.",
        "fix": "Use sane refresh/retry/expire/minimum per operations policy; increment serial on changes.",
        "refs": ["RFC 1035 §3.3.13", "RFC 2308"]
    },
    "SOA::SOA Lookup": {
        "explain": "Attempt to fetch the SOA record from default resolvers.",
        "why": "If the SOA can’t be fetched, the zone may be unreachable or misconfigured.",
        "fix": "Verify authoritative NS reachability, zone load, and delegation.",
        "refs": ["RFC 1035"]
    },
    "SOA::SOA from NS": {
        "explain": "Fetch the SOA serial individually from each authoritative nameserver.",
        "why": "Secondaries with old serials indicate replication lag or broken transfers.",
        "fix": "Fix zone transfers/NOTIFY; check ACLs and firewall rules between primaries and secondaries.",
        "refs": ["RFC 1996 (NOTIFY)", "RFC 5936 (AXFR)"]
    },
    "SOA::Serial Consistency": {
        "explain": "Compare SOA serial across all authoritative nameservers.",
        "why": "Inconsistent serials cause unpredictable answers and stale data.",
        "fix": "Repair replication and ensure all secondaries update promptly.",
        "refs": ["RFC 1035 §3.3.13"]
    },
    "SOA::Refresh": {
        "explain": "Validate the SOA refresh interval (how often secondaries poll for updates).",
        "why": "Too small wastes resources; too large delays propagation.",
        "fix": "Use a reasonable refresh (e.g., 15–60 min typical; your ops policy may vary).",
        "refs": ["Ops best practices"]
    },
    "SOA::Retry": {
        "explain": "Check retry interval (how long secondaries wait to retry after a failed refresh).",
        "why": "Retry should be smaller than refresh to recover from temporary failures.",
        "fix": "Set retry < refresh; common values are 5–15 minutes.",
        "refs": ["Ops best practices"]
    },
    "SOA::Expire": {
        "explain": "Validate expire (how long a secondary serves data without contacting primary).",
        "why": "Too small risks zones expiring during outages; too large can serve stale data for too long.",
        "fix": "Use a balanced expire time (often days to weeks) per your SLOs.",
        "refs": ["Ops best practices"]
    },
    "SOA::SOA TTL": {
        "explain": "Check the TTL of the SOA RRset.",
        "why": "Very low TTLs increase query load; very high TTLs slow control-plane changes.",
        "fix": "Choose a middle-ground TTL aligned with your change cadence (e.g., 1–24h).",
        "refs": ["RFC 2308"]
    },

    # ---- A / AAAA / CNAME / WWW ----
    "A Records::A Record": {
        "explain": "Fetch the apex A record(s) and TTL.",
        "why": "Without an A record (or equivalent), the apex won’t resolve for IPv4 clients.",
        "fix": "Add/maintain valid A records pointing to reachable servers.",
        "refs": ["RFC 1035 §3.4.1"]
    },
    "A Records::A Lookup": {
        "explain": "Attempt to resolve the apex A record(s).",
        "why": "Lookup failures typically indicate delegation or authoritative issues.",
        "fix": "Verify authoritative NS availability and zone contents.",
        "refs": ["RFC 1035"]
    },
    "A Records::Cross-NS Consistency": {
        "explain": "Compare apex A answers returned by different authoritative nameservers.",
        "why": "Inconsistent answers cause flapping user experience and cache confusion.",
        "fix": "Ensure all nameservers serve identical data for the apex.",
        "refs": ["RFC 2182"]
    },
    "IPv6::AAAA Record": {
        "explain": "Fetch the apex AAAA record(s) and TTL.",
        "why": "Without AAAA, IPv6-only clients or paths won’t reach your site.",
        "fix": "Add AAAA records when your service is reachable over IPv6.",
        "refs": ["RFC 3596"]
    },
    "CNAME::Host CNAME": {
        "explain": "Check common hosts (www, mail, ftp, webmail, smtp) for CNAMEs and follow targets.",
        "why": "CNAME chains must end at A/AAAA; broken links cause outages.",
        "fix": "Ensure CNAME targets exist and resolve; reduce unnecessary chains.",
        "refs": ["RFC 1034 §3.6.2"]
    },
    "Records::Apex CNAME": {
        "explain": "Detect a CNAME at the zone apex (illegal with SOA/NS present).",
        "why": "Violates standards and breaks many resolvers.",
        "fix": "Remove apex CNAME; use A/AAAA or provider ALIAS/ANAME.",
        "refs": ["RFC 1034 §3.6.2"]
    },
    "Records::Dangling CNAME": {
        "explain": "Follow CNAME target and ensure it eventually resolves to A/AAAA.",
        "why": "Dangling CNAMEs cause downtime and takeover risk if targets are reclaimed.",
        "fix": "Fix or remove CNAMEs whose targets do not resolve.",
        "refs": ["DNS hijack best practices"]
    },
    "Web::WWW Record": {
        "explain": "Check whether the common web hostname (www) resolves.",
        "why": "Many users try www.<domain>; lack of a record may be intentional but often isn’t.",
        "fix": "Add a www record (CNAME to apex or A/AAAA) if you intend to serve it.",
        "refs": ["Operational convention"]
    },

    # ---- Mail / Email Authentication ----
    "Mail::MX Records": {
        "explain": "Fetch MX records, priorities, and TTL.",
        "why": "MX directs inbound email; too few or misordered MX can reduce resilience.",
        "fix": "Publish at least two MX on distinct hosts/networks; set sensible priorities.",
        "refs": ["RFC 5321 §2.3.5"]
    },
    "Mail::MX Host": {
        "explain": "Resolve each MX hostname to its A/AAAA.",
        "why": "If an MX hostname doesn’t resolve, mail can’t be delivered.",
        "fix": "Ensure each MX has working A/AAAA and is reachable on port 25.",
        "refs": ["RFC 5321"]
    },
    "Mail::PTR": {
        "explain": "Check PTR (reverse DNS) for MX IPs.",
        "why": "Many receivers require valid PTR for anti-abuse; missing PTR harms deliverability.",
        "fix": "Ask your IP provider to set a matching PTR for each outbound MX IP.",
        "refs": ["RFC 1912 §2.1"]
    },
    "Mail::SPF Health": {
        "explain": "Validate SPF policy, ensure a single record, and approximate DNS lookup count.",
        "why": "Multiple or overly complex SPF can hard-fail at receivers; missing policy invites spoofing.",
        "fix": "Consolidate to one SPF; keep lookups ≤10; end with ~all or -all.",
        "refs": ["RFC 7208"]
    },
    "Mail::DMARC Policy": {
        "explain": "Parse DMARC policy, alignment, and reporting configuration.",
        "why": "DMARC mitigates spoofing; weak policies reduce protection and visibility.",
        "fix": "Adopt quarantine/reject when ready; validate external rua/ruf authorization tokens.",
        "refs": ["RFC 7489"]
    },
    "Mail::STARTTLS": {
        "explain": "Probe MX for STARTTLS support and perform TLS handshake.",
        "why": "STARTTLS encrypts mail in transit; broken TLS hurts deliverability and security.",
        "fix": "Enable STARTTLS and deploy valid, non-expired certificates covering MX hostnames.",
        "refs": ["RFC 3207"]
    },

    # ---- Policy ----
    "Policy::CAA": {
        "explain": "Check for CAA records controlling which CAs may issue certificates.",
        "why": "Prevents unauthorized issuance and supports compliance.",
        "fix": "Add 'issue'/'issuewild' for your chosen CA(s); optionally 'iodef' for alerts.",
        "refs": ["RFC 8659"]
    },
}

# Pattern rules to map dynamic check names to a static doc entry
_DOC_RULES = [
    # Nameservers
    {"category": "Nameservers", "prefix": "NS ",               "doc": "Nameservers::NS Host"},
    {"category": "Nameservers", "prefix": "Glue Consistency",  "doc": "Nameservers::Glue Consistency"},
    {"category": "Nameservers", "prefix": "Network Diversity", "doc": "Nameservers::Network Diversity"},
    {"category": "Nameservers", "prefix": "NS IP Sanity",      "doc": "Nameservers::NS IP Sanity"},
    # Performance / Security with per-NS names
    {"category": "Performance", "suffix": " Response",         "doc": "Performance::NS Response"},
    {"category": "Security",    "suffix": " Recursion",        "doc": "Security::Recursion"},
    {"category": "Security",    "suffix": " TCP 53",           "doc": "Security::TCP 53"},
    {"category": "Security",    "suffix": " EDNS",             "doc": "Security::EDNS"},
    {"category": "Security",    "suffix": " Lame",             "doc": "Security::Stealth/Lame NS"},
    {"category": "Security",    "suffix": " Stealth",          "doc": "Security::Stealth/Lame NS"},
    {"category": "Security",    "suffix": " Authority",        "doc": "Security::Authority Pass"},
    {"category": "Security",    "prefix": "Zone XFR ",         "doc": "Security::Zone XFR"},
    {"category": "Security",    "prefix": "Blacklist",         "doc": "Security::Blacklist"},
    # SOA
    {"category": "SOA",         "prefix": "SOA from ",         "doc": "SOA::SOA from NS"},
    {"category": "SOA",         "prefix": "SOA Record",        "doc": "SOA::SOA Record"},
    {"category": "SOA",         "prefix": "SOA Lookup",        "doc": "SOA::SOA Lookup"},
    {"category": "SOA",         "prefix": "Serial Consistency","doc": "SOA::Serial Consistency"},
    {"category": "SOA",         "prefix": "Refresh",           "doc": "SOA::Refresh"},
    {"category": "SOA",         "prefix": "Retry",             "doc": "SOA::Retry"},
    {"category": "SOA",         "prefix": "Expire",            "doc": "SOA::Expire"},
    {"category": "SOA",         "prefix": "SOA TTL",           "doc": "SOA::SOA TTL"},
    # A / AAAA / CNAME / Web
    {"category": "A Records",   "prefix": "A from ",           "doc": "A Records::Cross-NS Consistency"},
    {"category": "A Records",   "prefix": "A Record",          "doc": "A Records::A Record"},
    {"category": "A Records",   "prefix": "A Lookup",          "doc": "A Records::A Lookup"},
    {"category": "IPv6",        "prefix": "AAAA Record",       "doc": "IPv6::AAAA Record"},
    {"category": "CNAME",       "prefix": "",                  "doc": "CNAME::Host CNAME"},  # any CNAME line
    {"category": "Web",         "prefix": "WWW Record",        "doc": "Web::WWW Record"},
    # Mail
    {"category": "Mail",        "prefix": "MX Records",        "doc": "Mail::MX Records"},
    {"category": "Mail",        "prefix": "MX ",               "doc": "Mail::MX Host"},      # e.g., "MX mail.example.com"
    {"category": "Mail",        "prefix": "PTR ",              "doc": "Mail::PTR"},          # e.g., "PTR 203.0.113.4"
    {"category": "Mail",        "prefix": "SPF Health",        "doc": "Mail::SPF Health"},
    {"category": "Mail",        "prefix": "DMARC Policy",      "doc": "Mail::DMARC Policy"},
    {"category": "Mail",        "prefix": "STARTTLS ",         "doc": "Mail::STARTTLS"},
    # Records / Policy
    {"category": "Records",     "prefix": "Apex CNAME",        "doc": "Records::Apex CNAME"},
    {"category": "Records",     "prefix": "Dangling CNAME",    "doc": "Records::Dangling CNAME"},
    {"category": "Policy",      "prefix": "CAA",               "doc": "Policy::CAA"},
    # Parent (explicit)
    {"category": "Parent Zone", "prefix": "Parent NS Records", "doc": "Parent Zone::Parent NS Records"},
    {"category": "Parent Zone", "prefix": "Parent/Child Match","doc": "Parent Zone::Parent/Child Match"},
]

def _doc_for(category, name):
    """
    Return the docs dict for a given (category, name).
    Tries exact match first (Category::Name). If not present, runs prefix/suffix rules so
    dynamic names (e.g., 'NS ns1.example.com', 'A from ns2') still get rich documentation.
    """
    # 1) exact
    exact = CHECK_DOCS.get(f"{category}::{name}")
    if exact:
        return exact

    # 2) rule-based
    for rule in _DOC_RULES:
        if rule["category"] != category:
            continue
        pref = rule.get("prefix")
        suff = rule.get("suffix")
        if pref is not None and name.startswith(pref):
            return CHECK_DOCS.get(rule["doc"], {})
        if suff is not None and name.endswith(suff):
            return CHECK_DOCS.get(rule["doc"], {})

    # 3) default: no docs
    return {}



# ==================== DNS HELPER FUNCTIONS ====================

def get_ttl_from_answer(answer):
    """Extract TTL from a dnspython answer with fallbacks."""
    try:
        if answer and getattr(answer, "rrset", None) and getattr(answer.rrset, "ttl", None) is not None:
            return answer.rrset.ttl
        # fallback to response first answer section
        if answer and getattr(answer, "response", None) and answer.response.answer:
            return answer.response.answer[0].ttl
    except Exception:
        pass
    return None


def query_parent_nameservers(domain):
    """(Legacy) Query parent zone's authoritative nameservers for NS records (best-effort)."""
    try:
        parts = domain.split('.')
        if len(parts) < 2:
            return None
        tld = parts[-1]
        tld_ns = dns.resolver.resolve(tld, 'NS')
        for ns in tld_ns:
            try:
                ns_ip = str(dns.resolver.resolve(str(ns.target).rstrip('.'), 'A')[0])
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [ns_ip]
                parent_ns = resolver.resolve(domain, 'NS')
                return [str(ns.target).rstrip('.') for ns in parent_ns]
            except Exception:
                continue
        return None
    except Exception:
        return None


def _parent_ns_and_ips(domain):
    """
    Best-effort parent vantage:
    - Find a TLD nameserver IP
    - Ask it for NS at 'domain'
    - For in-bailiwick NS, fetch A/AAAA using same vantage (approximate 'glue')
    """
    try:
        parts = domain.split('.')
        if len(parts) < 2:
            return None, {}
        tld = parts[-1]
        tld_ns = dns.resolver.resolve(tld, 'NS')
        tld_ips = []
        for ns in tld_ns:
            try:
                ip = str(dns.resolver.resolve(str(ns.target).rstrip('.'), 'A')[0])
                tld_ips.append(ip)
            except Exception:
                continue
        if not tld_ips:
            return None, {}
        r = dns.resolver.Resolver()
        r.lifetime = 5
        r.timeout = 5
        r.nameservers = [tld_ips[0]]
        parent_ns = [str(x.target).rstrip('.') for x in r.resolve(domain, 'NS')]
        glue = {}
        for nsname in parent_ns:
            if nsname.endswith(f".{domain}"):
                glue_ips = []
                for t in ('A', 'AAAA'):
                    try:
                        ans = r.resolve(nsname, t)
                        glue_ips.extend([str(a) for a in ans])
                    except Exception:
                        pass
                glue[nsname] = glue_ips
        return parent_ns, glue
    except Exception:
        return None, {}


def check_glue_records(domain, nameservers):
    """Check if nameservers need glue records (in-bailiwick)."""
    glue_needed = []
    for ns in nameservers:
        if ns.endswith(domain):
            glue_needed.append(ns)
    return glue_needed


def get_asn_for_ip(ip):
    """Get ASN for an IP address via Team Cymru DNS (best-effort)."""
    try:
        reversed_ip = '.'.join(reversed(ip.split('.')))
        query = f'{reversed_ip}.origin.asn.cymru.com'
        answers = dns.resolver.resolve(query, 'TXT')
        for rdata in answers:
            txt = str(rdata).strip('"')
            parts = txt.split('|')
            if parts:
                return parts[0].strip()
    except Exception:
        return None
    return None


def _is_private_or_bogon(ip):
    try:
        ipobj = ipaddress.ip_address(ip)
        return (ipobj.is_private or ipobj.is_loopback or ipobj.is_link_local or
                ipobj.is_multicast or ipobj.is_reserved or ipobj.is_unspecified)
    except ValueError:
        return True


def _udp_query(ns_ip, qname, rdtype='SOA', rd=False, timeout=3, edns_payload=None, do_bit=False):
    import dns.message, dns.flags
    q = dns.message.make_query(qname, rdtype)
    if rd:
        q.flags |= dns.flags.RD
    else:
        q.flags &= ~dns.flags.RD
    if edns_payload:
        q.use_edns(edns=0, payload=edns_payload, request_payload=edns_payload)
        if do_bit:
            q.want_dnssec(True)
    r = dns.query.udp(q, ns_ip, timeout=timeout)
    return r


def _tcp_query(ns_ip, qname, rdtype='SOA', rd=False, timeout=5):
    import dns.message, dns.flags
    q = dns.message.make_query(qname, rdtype)
    if rd:
        q.flags |= dns.flags.RD
    else:
        q.flags &= ~dns.flags.RD
    return dns.query.tcp(q, ns_ip, timeout=timeout)


def _aa(resp):
    import dns.flags
    return bool(resp.flags & dns.flags.AA)


def _rcode_name(resp):
    import dns.rcode
    return dns.rcode.to_text(resp.rcode())


def test_open_recursion(ns_ip):
    """
    Return True ONLY if the server at ns_ip clearly performs recursion for us.
    Conditions to flag "open":
      - Probe #1 (RD=1): RA=1, AA=0, rcode in {NOERROR,NXDOMAIN}, and
        (has ANSWER or authority contains an SOA)
      - Probe #2 (RD=0) control: must NOT return a definitive NOERROR/NXDOMAIN with AA=0
    """
    try:
        import random, string
        import dns.message, dns.flags, dns.rcode, dns.rdatatype, dns.exception

        def _rand_name(suffix="com."):
            lbl = ''.join(random.choices(string.ascii_lowercase + string.digits, k=24))
            return f"recursion-test-{lbl}.{suffix}"

        def _ask(qname, rd, timeout=3):
            q = dns.message.make_query(qname, 'A')
            if rd:
                q.flags |= dns.flags.RD
            else:
                q.flags &= ~dns.flags.RD
            resp = dns.query.udp(q, ns_ip, timeout=timeout)
            if resp.flags & dns.flags.TC:
                resp = dns.query.tcp(q, ns_ip, timeout=timeout)
            return resp

        def _has_soa_in_authority(resp):
            return any(rrset.rdtype == dns.rdatatype.SOA for rrset in resp.authority)

        # Control: RD=0
        q0 = _rand_name("com.")
        try:
            r0 = _ask(q0, rd=False)
            r0_rcode = r0.rcode()
            r0_aa = bool(r0.flags & dns.flags.AA)
            if r0_rcode in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN) and not r0_aa:
                return False
        except dns.exception.Timeout:
            pass

        # Recursive probe: RD=1
        q1 = _rand_name("com.")
        r1 = _ask(q1, rd=True)
        ra = bool(r1.flags & dns.flags.RA)
        aa = bool(r1.flags & dns.flags.AA)
        rc = r1.rcode()

        if rc in (dns.rcode.REFUSED, dns.rcode.NOTIMP, dns.rcode.NOTAUTH):
            return False
        if not ra:
            return False
        if aa:
            return False
        if rc not in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN):
            return False

        answered = bool(r1.answer)
        auth_has_soa = _has_soa_in_authority(r1)
        if not (answered or auth_has_soa):
            return False

        return True
    except Exception:
        return False


# ==================== DNS HEALTH CHECK ====================

def check_dns_health(domain):
    """
    ULTIMATE DNS health check for a domain (IntoDNS-style output + extras)
    Returns detailed analysis dict
    """
    print(f"DEBUG: Starting ULTIMATE DNS health check for: {domain}")

    results = {
        'domain': domain,
        'timestamp': datetime.now().isoformat(),
        'checks': [],
        'summary': {'passed': 0, 'warnings': 0, 'errors': 0}
    }

    def add_check(category, name, status, message, details=None, doc_key=None, evidence=None):
        """Add a check result with optional IntoDNS-style documentation."""
        doc = _doc_for(category, name) if doc_key is None else CHECK_DOCS.get(doc_key, {})
        entry = {
            'category': category,
            'name': name,
            'status': status,
            'message': message,
            'details': details or []
        }
        if doc:
            entry['explain'] = doc.get('explain')
            entry['why'] = doc.get('why')
            entry['fix'] = doc.get('fix')
            entry['refs'] = doc.get('refs', [])
        if evidence:
            entry['evidence'] = evidence
        results['checks'].append(entry)

        if status == 'pass':
            results['summary']['passed'] += 1
        elif status == 'warn':
            results['summary']['warnings'] += 1
        elif status == 'error':
            results['summary']['errors'] += 1

    nameservers = []
    nameserver_ips = {}

    # Parent NS check (legacy simple) + better parent vantage
    parent_ns_simple = query_parent_nameservers(domain)
    parent_ns_list, parent_glue = _parent_ns_and_ips(domain)
    parent_ns_final = parent_ns_list or parent_ns_simple

    if parent_ns_final:
        add_check('Parent Zone', 'Parent NS Records', 'pass',
                  f'Parent zone lists {len(parent_ns_final)} nameserver(s)', parent_ns_final)

    # Nameserver checks
    try:
        ns_records = dns.resolver.resolve(domain, 'NS')
        nameservers = [str(ns.target).rstrip('.') for ns in ns_records]

        if len(nameservers) < 2:
            add_check('Nameservers', 'NS Count', 'warn',
                      f'Only {len(nameservers)} nameserver(s). Best practice: 2+', nameservers)
        else:
            add_check('Nameservers', 'NS Count', 'pass',
                      f'{len(nameservers)} nameservers found', nameservers)

        # Parent/child comparison
        if parent_ns_final:
            parent_set = set(parent_ns_final)
            child_set = set(nameservers)
            if parent_set == child_set:
                add_check('Parent Zone', 'Parent/Child Match', 'pass',
                          'Parent and child nameservers match')
            else:
                details = []
                if parent_set - child_set:
                    details.append(f'In parent not child: {", ".join(sorted(parent_set - child_set))}')
                if child_set - parent_set:
                    details.append(f'In child not parent: {", ".join(sorted(child_set - parent_set))}')
                add_check('Parent Zone', 'Parent/Child Match', 'error',
                          'Parent/child NS mismatch!', details)

        # Glue records needed?
        glue_needed = check_glue_records(domain, nameservers)
        if glue_needed:
            add_check('Nameservers', 'Glue Records', 'warn',
                      f'{len(glue_needed)} NS need glue records', glue_needed)
        else:
            add_check('Nameservers', 'Glue Records', 'pass',
                      'No glue records needed')

        # Resolve NS and get ASNs
        ns_asns = {}
        for ns in nameservers:
            try:
                ns_a = dns.resolver.resolve(ns, 'A')
                nameserver_ips[ns] = [str(ip) for ip in ns_a]
                add_check('Nameservers', f'NS {ns}', 'pass',
                          f'{ns} → {", ".join(nameserver_ips[ns])}')
                if nameserver_ips[ns]:
                    asn = get_asn_for_ip(nameserver_ips[ns][0])
                    if asn:
                        ns_asns[ns] = asn
            except Exception as e:
                add_check('Nameservers', f'NS {ns}', 'error', f'{ns} failed: {str(e)}')

        # ASN diversity
        if ns_asns:
            unique_asns = set(ns_asns.values())
            if len(unique_asns) == 1:
                add_check('Nameservers', 'Network Diversity', 'warn',
                          f'All NS on same network (ASN {list(unique_asns)[0]})',
                          [f'{ns}: ASN {asn}' for ns, asn in ns_asns.items()])
            else:
                add_check('Nameservers', 'Network Diversity', 'pass',
                          f'NS across {len(unique_asns)} network(s)',
                          [f'{ns}: ASN {asn}' for ns, asn in ns_asns.items()])

    except DNSException as e:
        add_check('Nameservers', 'NS Lookup', 'error', f'Failed: {str(e)}')

    # Glue consistency (Top-10 #1)
    if parent_glue and nameserver_ips:
        for ns in nameservers:
            if ns.endswith(f".{domain}"):
                child_ips = nameserver_ips.get(ns, [])
                parent_ips = parent_glue.get(ns, [])
                if parent_ips:
                    if set(child_ips) == set(parent_ips):
                        add_check('Nameservers', 'Glue Consistency', 'pass',
                                  f'{ns} glue matches child',
                                  evidence=[f'parent={parent_ips}', f'child={child_ips}'],
                                  doc_key="Nameservers::Glue Consistency")
                    else:
                        add_check('Nameservers', 'Glue Consistency', 'error',
                                  f'{ns} glue mismatch between parent and child',
                                  evidence=[f'parent={parent_ips}', f'child={child_ips}'],
                                  doc_key="Nameservers::Glue Consistency")

    # NS IP sanity (Top-10 #5)
    if nameserver_ips:
        bad_ns_ips = []
        for ns, ips in nameserver_ips.items():
            for ip in ips:
                if _is_private_or_bogon(ip):
                    bad_ns_ips.append((ns, ip))
        if bad_ns_ips:
            add_check('Nameservers', 'NS IP Sanity', 'error',
                      'One or more NS have non-public/bogon IPs.',
                      details=[f'{ns} → {ip}' for ns, ip in bad_ns_ips],
                      doc_key="Nameservers::NS IP Sanity")
        else:
            add_check('Nameservers', 'NS IP Sanity', 'pass',
                      'All NS IPs are public/routable',
                      doc_key="Nameservers::NS IP Sanity")

    # Per-NS performance + recursion + TCP/EDNS + Stealth/Lame
    for ns in nameservers:
        if ns not in nameserver_ips or not nameserver_ips[ns]:
            continue
        ns_ip = nameserver_ips[ns][0]

        # Response time
        try:
            start = time.time()
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [ns_ip]
            resolver.timeout = 5
            resolver.resolve(domain, 'SOA')
            rt = (time.time() - start) * 1000
            status = 'pass' if rt < 500 else 'warn'
            quality = 'excellent' if rt < 100 else ('good' if rt < 500 else 'slow')
            add_check('Performance', f'{ns} Response', status, f'{rt:.0f}ms ({quality})')
        except Exception:
            add_check('Performance', f'{ns} Response', 'error', f'{ns} timeout')

        # Open recursion
        try:
            if test_open_recursion(ns_ip):
                add_check('Security', f'{ns} Recursion', 'error',
                          f'{ns} allows open recursion - RISK!')
            else:
                add_check('Security', f'{ns} Recursion', 'pass',
                          f'{ns} denies recursion')
        except Exception:
            pass

        # TCP 53 (Top-10 #2)
        try:
            tcp_ok = False
            try:
                _ = _tcp_query(ns_ip, domain, rdtype='SOA', rd=False, timeout=5)
                tcp_ok = True
            except Exception:
                tcp_ok = False
            if tcp_ok:
                add_check('Security', f'{ns} TCP 53', 'pass', 'TCP/53 OK', doc_key="Security::TCP 53")
            else:
                add_check('Security', f'{ns} TCP 53', 'error', 'TCP/53 failed or blocked', doc_key="Security::TCP 53")
        except Exception as e:
            add_check('Security', f'{ns} TCP 53', 'error', f'TCP/53 probe error: {e}', doc_key="Security::TCP 53")

        # EDNS (Top-10 #3)
        try:
            ed = _udp_query(ns_ip, domain, rdtype='SOA', rd=False, timeout=3, edns_payload=1232, do_bit=False)
            rcode = _rcode_name(ed)
            add_check('Security', f'{ns} EDNS', 'pass', f'EDNS OK ({rcode})', doc_key="Security::EDNS")
        except Exception as e:
            add_check('Security', f'{ns} EDNS', 'warn', f'EDNS issue: {e}', doc_key="Security::EDNS")

        # Stealth/Lame (Top-10 #4)
        try:
            r = _udp_query(ns_ip, domain, rdtype='SOA', rd=False, timeout=3)
            if _aa(r):
                if ns not in nameservers:
                    add_check('Security', f'{ns} Stealth', 'warn',
                              'Authoritative but not listed in NS set',
                              doc_key="Security::Stealth/Lame NS")
                else:
                    add_check('Security', f'{ns} Authority', 'pass',
                              'Authoritative and listed')
            else:
                if ns in nameservers:
                    add_check('Security', f'{ns} Lame', 'error',
                              'Listed as NS but not authoritative (AA=0)',
                              doc_key="Security::Stealth/Lame NS")
        except Exception as e:
            if ns in nameservers:
                add_check('Security', f'{ns} Lame', 'error',
                          f'No authoritative response: {e}',
                          doc_key="Security::Stealth/Lame NS")

    # SOA checks
    soa_serials = {}
    try:
        soa_answer = dns.resolver.resolve(domain, 'SOA')
        primary_soa = soa_answer[0]
        soa_ttl = get_ttl_from_answer(soa_answer)
        ttl_info = [f'TTL: {soa_ttl}s'] if soa_ttl else []
        add_check('SOA', 'SOA Record', 'pass',
                  f'Primary: {primary_soa.mname}, Admin: {primary_soa.rname}',
                  [f'Serial: {primary_soa.serial}', f'Refresh: {primary_soa.refresh}s',
                   f'Retry: {primary_soa.retry}s', f'Expire: {primary_soa.expire}s',
                   f'Min TTL: {primary_soa.minimum}s'] + ttl_info)

        # Query each NS for SOA
        for ns in nameservers:
            if ns in nameserver_ips and nameserver_ips[ns]:
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = nameserver_ips[ns]
                    resolver.timeout = 5
                    soa = resolver.resolve(domain, 'SOA')[0]
                    soa_serials[ns] = soa.serial
                except Exception:
                    soa_serials[ns] = None
                    add_check('SOA', f'SOA from {ns}', 'error', f'{ns} no SOA (lame!)')

        # Serial consistency
        valid_serials = {s for s in soa_serials.values() if s is not None}
        if len(valid_serials) == 1:
            add_check('SOA', 'Serial Consistency', 'pass',
                      f'All NS return: {list(valid_serials)[0]}')
        elif len(valid_serials) > 1:
            add_check('SOA', 'Serial Consistency', 'error',
                      'NS have DIFFERENT serials!',
                      [f'{ns}: {s}' for ns, s in soa_serials.items() if s])

        # Timing checks
        if primary_soa.refresh < 1200 or primary_soa.refresh > 43200:
            add_check('SOA', 'Refresh', 'warn',
                      f'Refresh {primary_soa.refresh}s outside 1200-43200s')
        else:
            add_check('SOA', 'Refresh', 'pass', f'Refresh OK ({primary_soa.refresh}s)')

        if primary_soa.retry < primary_soa.refresh:
            add_check('SOA', 'Retry', 'pass',
                      f'Retry ({primary_soa.retry}s) < Refresh ✓')
        else:
            add_check('SOA', 'Retry', 'warn', 'Retry should be < Refresh')

        if primary_oa := primary_soa:
            if primary_oa.expire > primary_oa.refresh * 2:
                add_check('SOA', 'Expire', 'pass', f'Expire OK ({primary_oa.expire}s)')
            else:
                add_check('SOA', 'Expire', 'warn', f'Expire may be low ({primary_oa.expire}s)')

        if soa_ttl:
            if soa_ttl < 3600:
                add_check('SOA', 'SOA TTL', 'warn', f'TTL low ({soa_ttl}s)')
            elif soa_ttl > 86400:
                add_check('SOA', 'SOA TTL', 'warn', f'TTL high ({soa_ttl}s)')
            else:
                add_check('SOA', 'SOA TTL', 'pass', f'TTL OK ({soa_ttl}s)')

    except DNSException as e:
        add_check('SOA', 'SOA Lookup', 'error', f'Failed: {str(e)}')

    # A records
    a_ips = []
    try:
        a_answer = dns.resolver.resolve(domain, 'A')
        a_ips = [str(a) for a in a_answer]
        a_ttl = get_ttl_from_answer(a_answer)
        ttl_info = f' (TTL: {a_ttl}s)' if a_ttl else ''
        add_check('A Records', 'A Record', 'pass',
                  f'{len(a_ips)} A record(s){ttl_info}', a_ips)
        # Cross-NS consistency
        for ns in nameservers[:3]:
            if ns in nameserver_ips and nameserver_ips[ns]:
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = nameserver_ips[ns]
                    resolver.timeout = 5
                    ns_a = resolver.resolve(domain, 'A')
                    ns_ips = set(str(a) for a in ns_a)
                    if ns_ips == set(a_ips):
                        add_check('A Records', f'A from {ns}', 'pass', 'Consistent')
                    else:
                        add_check('A Records', f'A from {ns}', 'warn', 'Different!')
                except Exception:
                    pass
    except dns.resolver.NoAnswer:
        add_check('A Records', 'A Record', 'warn', 'No A records')
    except DNSException as e:
        add_check('A Records', 'A Lookup', 'error', f'Failed: {str(e)}')

    # AAAA (IPv6)
    try:
        aaaa_answer = dns.resolver.resolve(domain, 'AAAA')
        aaaa_ips = [str(a) for a in aaaa_answer]
        aaaa_ttl = get_ttl_from_answer(aaaa_answer)
        ttl_info = f' (TTL: {aaaa_ttl}s)' if aaaa_ttl else ''
        add_check('IPv6', 'AAAA Record', 'pass',
                  f'{len(aaaa_ips)} IPv6{ttl_info} - IPv6 ready! 🎉', aaaa_ips)
    except dns.resolver.NoAnswer:
        add_check('IPv6', 'AAAA Record', 'warn', 'No IPv6 support')
    except Exception:
        pass

    # CAA (Top-10 #6)
    try:
        caa_ans = dns.resolver.resolve(domain, 'CAA')
        caa_vals = [str(rr) for rr in caa_ans]
        add_check('Policy', 'CAA', 'pass', f'CAA present ({len(caa_vals)})', caa_vals, doc_key="Policy::CAA")
    except DNSException:
        add_check('Policy', 'CAA', 'warn', 'No CAA records', doc_key="Policy::CAA")

    # Common CNAME sanity (and later dangling detection block)
    for sub in ['www', 'mail', 'ftp', 'webmail', 'smtp']:
        full = f'{sub}.{domain}'
        try:
            cname_answer = dns.resolver.resolve(full, 'CNAME')
            target = str(cname_answer[0].target).rstrip('.')
            ttl = get_ttl_from_answer(cname_answer)
            ttl_info = f' (TTL: {ttl}s)' if ttl else ''
            add_check('CNAME', f'{sub}', 'pass', f'CNAME → {target}{ttl_info}')
        except dns.resolver.NoAnswer:
            try:
                a_answer = dns.resolver.resolve(full, 'A')
                ips = [str(a) for a in a_answer]
                ttl = get_ttl_from_answer(a_answer)
                ttl_info = f' (TTL: {ttl}s)' if ttl else ''
                add_check('CNAME', f'{sub}', 'pass', f'A record{ttl_info}', ips)
            except Exception:
                pass
        except Exception:
            pass

    # MX checks (with STARTTLS) and PTRs
    mx_ips = {}
    try:
        mx_answer = dns.resolver.resolve(domain, 'MX')
        mx_list = [(mx.preference, str(mx.exchange).rstrip('.')) for mx in mx_answer]
        mx_list.sort()
        mx_ttl = get_ttl_from_answer(mx_answer)
        ttl_info = f' (TTL: {mx_ttl}s)' if mx_ttl else ''

        if len(mx_list) == 0:
            add_check('Mail', 'MX Records', 'warn', 'No MX - email broken')
        elif len(mx_list) == 1:
            add_check('Mail', 'MX Records', 'warn', f'Only 1 MX{ttl_info}',
                      [f'Priority {p}: {h}' for p, h in mx_list])
        else:
            add_check('Mail', 'MX Records', 'pass', f'{len(mx_list)} MX{ttl_info}',
                      [f'Priority {p}: {h}' for p, h in mx_list])

        # Resolve MX -> IPs
        for pref, mx_host in mx_list:
            try:
                mx_a = dns.resolver.resolve(mx_host, 'A')
                mx_ips[mx_host] = [str(ip) for ip in mx_a]
                add_check('Mail', f'MX {mx_host}', 'pass',
                          f'{mx_host} → {", ".join(mx_ips[mx_host])}')
            except Exception:
                add_check('Mail', f'MX {mx_host}', 'error', f'{mx_host} no resolve')

        # PTR checks
        for mx_host, ips in mx_ips.items():
            for ip in ips[:1]:
                try:
                    rev = dns.reversename.from_address(ip)
                    ptr = dns.resolver.resolve(rev, 'PTR')
                    ptr_hosts = [str(p).rstrip('.') for p in ptr]
                    add_check('Mail', f'PTR {ip}', 'pass', f'PTR: {", ".join(ptr_hosts)}')
                except dns.resolver.NXDOMAIN:
                    add_check('Mail', f'PTR {ip}', 'warn', f'No PTR for {ip}')
                except Exception:
                    pass

        # SMTP STARTTLS (Top-10 #9) - limit to first 3 MX
        for mx_host, ips in list(mx_ips.items())[:3]:
            for ip in ips[:1]:
                try:
                    sock = socket.create_connection((ip, 25), timeout=10)
                    banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.sendall(b"EHLO example.com\r\n")
                    ehlo = sock.recv(2048).decode('utf-8', errors='ignore')
                    has_starttls = 'STARTTLS' in ehlo.upper()
                    if has_starttls:
                        sock.sendall(b"STARTTLS\r\n")
                        resp = sock.recv(1024).decode('utf-8', errors='ignore')
                        if resp.startswith('220'):
                            context = ssl.create_default_context()
                            tls_sock = context.wrap_socket(sock, server_hostname=mx_host)
                            cert = tls_sock.getpeercert() or {}
                            subj = dict(x[0] for x in cert.get('subject', ()))
                            cn = subj.get('commonName', '')
                            add_check('Mail', f'STARTTLS {mx_host}', 'pass',
                                      'STARTTLS OK',
                                      evidence=[f'CN={cn}', f'Banner={banner.strip()[:80]}'],
                                      doc_key="Mail::STARTTLS")
                            try:
                                tls_sock.close()
                            except Exception:
                                pass
                        else:
                            add_check('Mail', f'STARTTLS {mx_host}', 'error',
                                      'STARTTLS advertised but failed to start',
                                      evidence=[resp.strip()],
                                      doc_key="Mail::STARTTLS")
                    else:
                        add_check('Mail', f'STARTTLS {mx_host}', 'warn',
                                  'No STARTTLS advertised',
                                  evidence=[f'Banner={banner.strip()[:80]}'],
                                  doc_key="Mail::STARTTLS")
                    try:
                        sock.close()
                    except Exception:
                        pass
                except Exception as e:
                    add_check('Mail', f'STARTTLS {mx_host}', 'warn',
                              f'Port 25 probe failed: {e}',
                              doc_key="Mail::STARTTLS")
                break

    except dns.resolver.NoAnswer:
        add_check('Mail', 'MX Records', 'warn', 'No MX records')
    except DNSException as e:
        add_check('Mail', 'MX Lookup', 'error', f'Failed: {str(e)}')

    # SPF Health (Top-10 #7)
    try:
        txt_answer = dns.resolver.resolve(domain, 'TXT')
        txt_ttl = get_ttl_from_answer(txt_answer)
        spf_records = []
        for txt in txt_answer:
            txt_str = str(txt).strip('"')
            if txt_str.lower().startswith('v=spf1'):
                spf_records.append(txt_str)

        if not spf_records:
            add_check('Mail', 'SPF Health', 'warn', 'No SPF - recommend adding',
                      doc_key="Mail::SPF Health")
        elif len(spf_records) > 1:
            add_check('Mail', 'SPF Health', 'error', 'Multiple SPF records found',
                      spf_records, doc_key="Mail::SPF Health")
        else:
            spf = spf_records[0]
            # heuristic lookup counting
            count = spf.count('include:') + spf.count('exists:') + spf.count('redirect=')
            count += sum(1 for t in spf.split() if t == 'a' or t == 'mx' or t.startswith('a:') or t.startswith('mx:') or t.startswith('ptr'))
            policy = ('+all' if '+all' in spf else ('-all' if '-all' in spf else ('~all' if '~all' in spf else 'none')))
            ttl_info = f' (TTL: {txt_ttl}s)' if txt_ttl else ''
            ev = [f'lookups≈{count}', f'policy={policy}', spf]
            if count > 10:
                add_check('Mail', 'SPF Health', 'error', f'SPF exceeds 10 DNS lookups{ttl_info}', evidence=ev,
                          doc_key="Mail::SPF Health")
            elif policy == '+all':
                add_check('Mail', 'SPF Health', 'error', f'SPF uses +all (overly permissive){ttl_info}', evidence=ev,
                          doc_key="Mail::SPF Health")
            elif policy == 'none':
                add_check('Mail', 'SPF Health', 'warn', f'SPF missing terminal ~all or -all{ttl_info}', evidence=ev,
                          doc_key="Mail::SPF Health")
            else:
                add_check('Mail', 'SPF Health', 'pass', f'SPF OK{ttl_info}', evidence=ev,
                          doc_key="Mail::SPF Health")
    except Exception as e:
        add_check('Mail', 'SPF Health', 'warn', f'SPF check error: {e}', doc_key="Mail::SPF Health")

    # DMARC depth (Top-10 #8)
    try:
        dmarc_answer = dns.resolver.resolve(f'_dmarc.{domain}', 'TXT')
        txts = [''.join([part.strip('"') for part in str(t).split()]) for t in dmarc_answer]
        pol = 'missing'
        ev = []
        for t in txts:
            if t.lower().startswith('v=dmarc1'):
                ev.append(t)
                tags = dict(kv.split('=', 1) for kv in [kv for kv in t.split(';') if '=' in kv])
                pol = tags.get('p', 'none').strip()
                adkim = tags.get('adkim', 'r').strip()
                aspf = tags.get('aspf', 'r').strip()
                rua  = tags.get('rua', '').strip()
                ev.extend([f"p={pol}", f"adkim={adkim}", f"aspf={aspf}", f"rua={rua}"])
                break
        if pol == 'missing':
            add_check('Mail', 'DMARC Policy', 'warn', 'No DMARC - strongly recommended',
                      doc_key="Mail::DMARC Policy")
        else:
            if pol == 'reject':
                add_check('Mail', 'DMARC Policy', 'pass', 'Policy: reject (strong)',
                          evidence=ev, doc_key="Mail::DMARC Policy")
            elif pol == 'quarantine':
                add_check('Mail', 'DMARC Policy', 'pass', 'Policy: quarantine (good)',
                          evidence=ev, doc_key="Mail::DMARC Policy")
            else:
                add_check('Mail', 'DMARC Policy', 'warn', 'Policy: none (monitor only)',
                          evidence=ev, doc_key="Mail::DMARC Policy")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        add_check('Mail', 'DMARC Policy', 'warn', 'No DMARC - strongly recommended',
                  doc_key="Mail::DMARC Policy")
    except Exception as e:
        add_check('Mail', 'DMARC Policy', 'warn', f'DMARC check error: {e}',
                  doc_key="Mail::DMARC Policy")

    # WWW check
    try:
        www_answer = dns.resolver.resolve(f'www.{domain}', 'A')
        www_ttl = get_ttl_from_answer(www_answer)
        ttl_info = f' (TTL: {www_ttl}s)' if www_ttl else ''
        add_check('Web', 'WWW Record', 'pass', f'www resolves{ttl_info}',
                  [str(a) for a in www_answer])
    except dns.resolver.NXDOMAIN:
        add_check('Web', 'WWW Record', 'warn', f'www.{domain} does not exist')
    except Exception:
        pass

    # Blacklist check (first A only, informational)
    if 'A Records' in [c['category'] for c in results['checks']] and a_ips:
        check_ip = a_ips[0]
        blacklists = ['zen.spamhaus.org', 'bl.spamcop.net', 'b.barracudacentral.org',
                      'dnsbl.sorbs.net', 'cbl.abuseat.org']
        listed = []
        for bl in blacklists:
            try:
                rev_ip = '.'.join(reversed(check_ip.split('.')))
                dns.resolver.resolve(f'{rev_ip}.{bl}', 'A')
                listed.append(bl)
            except Exception:
                pass
        if listed:
            add_check('Security', 'Blacklist', 'error',
                      f'IP {check_ip} on {len(listed)} blacklist(s)!',
                      [f'Listed: {", ".join(listed)}'])
        else:
            add_check('Security', 'Blacklist', 'pass', f'IP {check_ip} not blacklisted')

    # Zone transfer test
    for ns in nameservers[:2]:
        if ns in nameserver_ips and nameserver_ips[ns]:
            try:
                dns.zone.from_xfr(dns.query.xfr(nameserver_ips[ns][0], domain, timeout=5))
                add_check('Security', f'Zone XFR {ns}', 'error',
                          f'Zone transfer ALLOWED on {ns} - RISK!',
                          ['Restrict zone transfers'])
            except Exception:
                add_check('Security', f'Zone XFR {ns}', 'pass', f'Zone XFR restricted on {ns}')

    # Apex CNAME (illegal) (Top-10 #10)
    try:
        apex_cname = dns.resolver.resolve(domain, 'CNAME')
        add_check('Records', 'Apex CNAME', 'error', 'Apex has a CNAME (illegal)',
                  [str(r.target).rstrip('.') for r in apex_cname], doc_key="Records::Apex CNAME")
    except DNSException:
        add_check('Records', 'Apex CNAME', 'pass', 'No apex CNAME', doc_key="Records::Apex CNAME")

    # Dangling CNAMEs for common hosts (Top-10 #10)
    def _dangling(name):
        try:
            cname_answer = dns.resolver.resolve(name, 'CNAME')
            target = str(cname_answer[0].target).rstrip('.')
            try:
                _ = dns.resolver.resolve(target, 'A')
                return False, target
            except Exception:
                try:
                    _ = dns.resolver.resolve(target, 'AAAA')
                    return False, target
                except Exception:
                    return True, target
        except dns.resolver.NoAnswer:
            return False, None
        except Exception:
            return False, None

    for sub in ['www', 'mail', 'ftp', 'webmail', 'smtp']:
        fq = f'{sub}.{domain}'
        try:
            is_dangling, tgt = _dangling(fq)
            if is_dangling:
                add_check('Records', f'Dangling CNAME {sub}', 'error',
                          f'{fq} CNAME target does not resolve', evidence=[f'target={tgt}'],
                          doc_key="Records::Dangling CNAME")
        except Exception:
            pass

    print(f"DEBUG: DNS check complete. Summary: {results['summary']}")
    return results


def format_dns_health_output(results):
    """Format DNS health check results into readable text with docs."""
    output = []
    output.append("=" * 80)
    output.append(f"DNS HEALTH CHECK: {results['domain']}")
    output.append(f"Timestamp: {results['timestamp']}")
    output.append("=" * 80)
    output.append("")

    summary = results['summary']
    output.append(f"SUMMARY: ✓ {summary['passed']} Passed | "
                  f"⚠ {summary['warnings']} Warnings | "
                  f"✗ {summary['errors']} Errors")
    output.append("")
    output.append("=" * 80)
    output.append("")

    categories = {}
    for check in results['checks']:
        categories.setdefault(check['category'], []).append(check)

    for category, checks in categories.items():
        output.append(f"\n{'='*80}")
        output.append(f"{category.upper()}")
        output.append('='*80)
        for check in checks:
            icon = {'pass': '✓', 'warn': '⚠', 'error': '✗'}.get(check['status'], '?')
            output.append(f"\n[{icon}] {check['name']}")
            output.append(f"    {check['message']}")
            if check.get('explain'):
                output.append(f"    What we tested: {check['explain']}")
            if check.get('why'):
                output.append(f"    Why it matters: {check['why']}")
            if check.get('fix'):
                output.append(f"    How to fix:     {check['fix']}")
            if check.get('refs'):
                output.append(f"    Refs:           " + "; ".join(check['refs']))
            if check.get('evidence'):
                ev = check['evidence']
                if isinstance(ev, list):
                    for line in ev:
                        output.append(f"    Evidence:       {line}")
                else:
                    output.append(f"    Evidence:       {ev}")
            if check.get('details'):
                for detail in check['details']:
                    output.append(f"    - {detail}")

    output.append("\n" + "=" * 80)
    output.append("DNS Health Check Complete")
    output.append("=" * 80)
    return "\n".join(output)


# ==================== TOOL EXECUTION ====================

def execute_tool(tool_name, target=None, parameters=None, timeout=None):
    """Execute a diagnostic tool and capture output"""
    if timeout is None:
        tool_timeouts = {
            'traceroute': 180,
            'pathping': 300,
            'ping': 30,
            'whois_domain': 60,
            'whois_ip': 60,
            'nslookup': 30,
            'dns_health': 120,  # slightly higher for TLS/EDNS/TCP
        }
        timeout = tool_timeouts.get(tool_name, 60)

    start_time = time.time()

    try:
        if tool_name == 'dns_health':
            try:
                print(f"DEBUG: Executing DNS health check for: {target}")
                dns_results = check_dns_health(target)
                print(f"DEBUG: DNS check complete. Summary: {dns_results['summary']}")
                output = format_dns_health_output(dns_results)
                execution_time = time.time() - start_time
                return {
                    'success': True,
                    'exit_code': 0,
                    'output': output,
                    'error': '',
                    'execution_time': execution_time,
                    'command': f'DNS Health Check: {target}',
                    'parsed_data': dns_results
                }
            except Exception as e:
                print(f"DEBUG: DNS health check failed: {str(e)}")
                import traceback
                traceback.print_exc()
                execution_time = time.time() - start_time
                return {
                    'success': False,
                    'exit_code': -1,
                    'output': '',
                    'error': f'DNS Health Check failed: {str(e)}',
                    'execution_time': execution_time,
                    'command': f'DNS Health Check: {target}'
                }

        # Build and execute command for other tools
        cmd, command_string = build_tool_command(tool_name, target, parameters)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        execution_time = time.time() - start_time
        return {
            'success': result.returncode == 0,
            'exit_code': result.returncode,
            'output': result.stdout,
            'error': result.stderr,
            'execution_time': execution_time,
            'command': command_string
        }

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        return {
            'success': False,
            'exit_code': -1,
            'output': '',
            'error': f'Command timed out after {timeout} seconds',
            'execution_time': execution_time,
            'command': command_string if 'command_string' in locals() else 'N/A'
        }

    except FileNotFoundError as e:
        execution_time = time.time() - start_time
        return {
            'success': False,
            'exit_code': -1,
            'output': '',
            'error': f'Tool not found: {str(e)}',
            'execution_time': execution_time,
            'command': 'N/A'
        }

    except Exception as e:
        execution_time = time.time() - start_time
        return {
            'success': False,
            'exit_code': -1,
            'output': '',
            'error': f'Error executing tool: {str(e)}',
            'execution_time': execution_time,
            'command': command_string if 'command_string' in locals() else 'N/A'
        }


# ==================== OUTPUT PARSERS ====================

def parse_ping(output):
    """Parse ping output to extract key metrics"""
    lines = output.split('\n')
    result = {
        'packets_sent': 0,
        'packets_received': 0,
        'packets_lost': 0,
        'loss_percentage': 0,
        'min_time': None,
        'max_time': None,
        'avg_time': None
    }
    try:
        for line in lines:
            if 'Packets: Sent' in line:
                parts = line.split(',')
                result['packets_sent'] = int(parts[0].split('=')[1].strip())
                result['packets_received'] = int(parts[1].split('=')[1].strip())
                result['packets_lost'] = int(parts[2].split('=')[1].strip().split()[0])
                result['loss_percentage'] = int(parts[2].split('(')[1].split('%')[0])
            if 'Minimum' in line and 'Maximum' in line:
                parts = line.split(',')
                result['min_time'] = int(parts[0].split('=')[1].strip().replace('ms', ''))
                result['max_time'] = int(parts[1].split('=')[1].strip().replace('ms', ''))
                result['avg_time'] = int(parts[2].split('=')[1].strip().replace('ms', ''))
    except Exception:
        pass
    return result


def parse_traceroute(output):
    """Parse traceroute output to extract hops"""
    lines = output.split('\n')
    hops = []
    try:
        for line in lines:
            line = line.strip()
            if line and line[0].isdigit():
                parts = line.split()
                if len(parts) >= 2:
                    hops.append({'number': parts[0], 'data': ' '.join(parts[1:])})
    except Exception:
        pass
    return {'hops': hops, 'hop_count': len(hops)}


def parse_nslookup(output):
    """Parse nslookup output"""
    lines = output.split('\n')
    result = {'server': None, 'addresses': []}
    try:
        for line in lines:
            if 'Server:' in line:
                result['server'] = line.split('Server:')[1].strip()
            if 'Address:' in line and 'Server' not in line:
                result['addresses'].append(line.split('Address:')[1].strip())
    except Exception:
        pass
    return result


def parse_tool_output(tool_name, output):
    """Parse tool output based on tool type"""
    tool_config = get_tool_config(tool_name)
    if not tool_config:
        return None
    parser_name = tool_config.get('output_parser')
    if not parser_name:
        return None
    parsers = {
        'parse_ping': parse_ping,
        'parse_traceroute': parse_traceroute,
        'parse_nslookup': parse_nslookup
    }
    parser_func = parsers.get(parser_name)
    if parser_func:
        return parser_func(output)
    return None


# ==================== STATISTICS ====================

def create_tool_history_summary(executions):
    """Create summary statistics from tool execution history"""
    if not executions:
        return {
            'total_executions': 0,
            'success_count': 0,
            'failure_count': 0,
            'success_rate': 0,
            'avg_execution_time': 0,
            'tools_used': {},
            'targets_tested': {}
        }

    total = len(executions)
    success = sum(1 for e in executions if e.success)
    failure = total - success
    avg_time = sum(e.execution_time for e in executions if e.execution_time) / total

    tools_used = {}
    for e in executions:
        tools_used[e.tool_name] = tools_used.get(e.tool_name, 0) + 1

    targets_tested = {}
    for e in executions:
        if getattr(e, 'target', None):
            targets_tested[e.target] = targets_tested.get(e.target, 0) + 1

    return {
        'total_executions': total,
        'success_count': success,
        'failure_count': failure,
        'success_rate': round((success / total) * 100, 1),
        'avg_execution_time': round(avg_time, 2),
        'tools_used': tools_used,
        'targets_tested': targets_tested
    }
