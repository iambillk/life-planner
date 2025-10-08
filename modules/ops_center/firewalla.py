"""
Operations Command Center - Firewalla MSP API Integration
Version: 1.0.1
Last Modified: 2025-10-05
Author: Billas
Description: Firewalla MSP API integration for security monitoring and threat management

File: /modules/ops_center/firewalla.py

CHANGELOG:
- 1.0.1 (2025-10-05): FIX parse of v2 responses:
                      alarms/flows/rules now read {count, results}
                      rules 'active' uses status == "active"
                      tolerate missing hitCount
- 1.0.0 (2025-01-XX): Initial implementation with core MSP API v2 support
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app
import json

class FirewallaAPI:
    """
    Firewalla MSP API v2 integration.
    """

    def __init__(self, domain: str = None, token: str = None):
        self.domain = domain or current_app.config.get('FIREWALLA_MSP_DOMAIN', 'totalchoice.firewalla.net')
        self.token = token or current_app.config.get('FIREWALLA_API_TOKEN', '')
        self.base_url = f"https://{self.domain}/v2"
        self.headers = {
            'Authorization': f'Token {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.timeout = current_app.config.get('FIREWALLA_TIMEOUT', 10)
        self._cache = {}
        self._cache_ttl = current_app.config.get('FIREWALLA_CACHE_TTL', 60)  # seconds

    def _api_call(self, method: str, endpoint: str, params: Dict = None) -> Optional[Any]:
        """
        Call Firewalla MSP API with a tiny in-memory cache.
        """
        cache_key = f"{method}:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).seconds < self._cache_ttl:
                return cached_data

        try:
            url = f"{self.base_url}{endpoint}"
            if method == 'GET':
                resp = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
            else:
                resp = requests.request(method, url, headers=self.headers, json=params, timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                self._cache[cache_key] = (datetime.now(), data)
                return data

            print(f"[Firewalla] API error {resp.status_code} on {endpoint}: {resp.text[:200]}")
            return None

        except requests.exceptions.Timeout:
            print(f"[Firewalla] Timeout calling {endpoint}")
            return None
        except Exception as e:
            print(f"[Firewalla] Error calling {endpoint}: {e}")
            return None

    # ==================== ALARMS ====================

    def get_alarms(self, hours: int = 24) -> Dict:
        """
        Returns dict: {'count', 'latest', 'alarms'}
        """
        # Prefer sorted, capped list
        params = {'sortBy': 'ts:desc', 'limit': 200}
        response = self._api_call('GET', '/alarms', params)

        # Fallback with time window if needed
        if not response:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            params = {
                'sortBy': 'ts:desc',
                'limit': 200,
                'query': f'ts>={int(start_time.timestamp())} AND ts<={int(end_time.timestamp())}'
            }
            response = self._api_call('GET', '/alarms', params)

        if not response:
            return {'count': 0, 'latest': 'No Recent Alerts', 'alarms': []}

        # v2 shape: { count, results: [...] }
        results = response.get('results', []) if isinstance(response, dict) else []
        latest_msg = 'No Recent Alerts'
        if results:
            top = results[0]
            latest_msg = top.get('message') or top.get('type', 'Unknown Alert')
            if isinstance(latest_msg, str) and len(latest_msg) > 50:
                latest_msg = latest_msg[:47] + '...'

        return {
            'count': response.get('count', len(results)) if isinstance(response, dict) else len(results),
            'latest': latest_msg,
            'alarms': results[:100]
        }

    # ==================== BOXES / DEVICES ====================

    def get_boxes(self) -> List[Dict]:
        boxes = self._api_call('GET', '/boxes')
        if not boxes:
            return []
        box_list = boxes if isinstance(boxes, list) else boxes.get('boxes', [])
        result = []
        for b in box_list:
            result.append({
                'id': b.get('gid'),
                'name': b.get('name', 'Unknown'),
                'model': b.get('model', 'Unknown'),
                'online': b.get('online', False),
                'version': b.get('version', 'Unknown'),
                'public_ip': b.get('publicIP', 'N/A'),
                'mode': b.get('mode', 'Unknown'),
                'device_count': b.get('deviceCount', 0),
                'alarm_count': b.get('alarmCount', 0)
            })
        return result

    def get_devices(self) -> Dict:
        devices = self._api_call('GET', '/devices')
        if not devices:
            return {'total': 0, 'online': 0, 'offline': 0}
        device_list = devices if isinstance(devices, list) else devices.get('devices', [])
        online = sum(1 for d in device_list if d.get('online', False))
        return {'total': len(device_list), 'online': online, 'offline': len(device_list) - online}

    # ==================== FLOWS ====================

    def get_flows(self, hours: int = 1) -> Dict:
        """
        Returns dict: {'total','blocked','allowed'}
        """
        params = {'sortBy': 'ts:desc', 'limit': 200}
        response = self._api_call('GET', '/flows', params)

        if not response:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            params = {
                'sortBy': 'ts:desc',
                'limit': 200,
                'query': f'ts>={int(start_time.timestamp())} AND ts<={int(end_time.timestamp())}'
            }
            response = self._api_call('GET', '/flows', params)

        if not response:
            return {'total': 0, 'blocked': 0, 'allowed': 0}

        # v2 shape: { count, results: [...] }
        results = response.get('results', []) if isinstance(response, dict) else []
        blocked = sum(1 for f in results if f.get('block') is True)
        total = response.get('count', len(results)) if isinstance(response, dict) else len(results)
        return {'total': total, 'blocked': blocked, 'allowed': max(total - blocked, 0)}

    # ==================== RULES ====================

    def get_rules(self) -> Dict:
        """
        Returns dict: {'total','active','hits_today'}
        """
        response = self._api_call('GET', '/rules')  # MSP 2.7+ returns {count, results}
        if not response:
            return {'total': 0, 'active': 0, 'hits_today': 0}

        results = response.get('results', []) if isinstance(response, dict) else []
        total = response.get('count', len(results)) if isinstance(response, dict) else len(results)

        # 'active' is status == "active" (compat: also accept enabled==True)
        active = 0
        hits = 0
        for r in results:
            status = (r.get('status') or '').lower()
            if status == 'active' or r.get('enabled') is True:
                active += 1
            # tolerate missing hitCount
            hits += int(r.get('hitCount', 0) or 0)

        return {'total': total, 'active': active, 'hits_today': hits}

    # ==================== TARGET LIST CONTROL ====================

    def _target_list_id(self) -> str:
        tlid = current_app.config.get('FIREWALLA_TARGET_LIST_ID', '').strip()
        if not tlid:
            raise RuntimeError("FIREWALLA_TARGET_LIST_ID not configured")
        return tlid

    def get_target_list(self) -> Optional[Dict]:
        """Fetch the full target list object (contains .targets array)."""
        tlid = self._target_list_id()
        return self._api_call('GET', f'/target-lists/{tlid}')

    def add_block_target(self, target: str) -> bool:
        """Append an IP/domain to the target list and PATCH it back."""
        if not target or not isinstance(target, str):
            return False
        cur = self.get_target_list()
        if not cur or 'targets' not in cur or not isinstance(cur['targets'], list):
            return False
        targets = list({*cur.get('targets', []), target})  # unique
        payload = dict(cur)
        payload['targets'] = targets
        tlid = self._target_list_id()
        resp = self._api_call('PATCH', f'/target-lists/{tlid}', payload)
        return bool(resp)

    def remove_block_target(self, target: str) -> bool:
        """Remove an IP/domain from the target list and PATCH it back."""
        if not target or not isinstance(target, str):
            return False
        cur = self.get_target_list()
        if not cur or 'targets' not in cur or not isinstance(cur['targets'], list):
            return False
        targets = [t for t in cur.get('targets', []) if t != target]
        payload = dict(cur)
        payload['targets'] = targets
        tlid = self._target_list_id()
        resp = self._api_call('PATCH', f'/target-lists/{tlid}', payload)
        return bool(resp)
    
    # ==================== ABNORMAL UPLOAD ALARMS ====================
    def get_abnormal_upload_alarms(self, hours: int = 24, limit: int = 100) -> Dict:
        """
        Return alarms likely classified as 'Abnormal Upload' in the last N hours.
        Uses API time-range + server filter hints, then defensively post-filters.
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Ask server for time-bounded alarms (desc) with a generous page
        params = {
            'sortBy': 'ts:desc',
            'limit': min(max(int(limit), 1), 200),  # cap to a single page
            # Server-side hint (not strictly required; we still post-filter)
            # Some tenants surface 'type' or 'message' fields; we rely on both.
            'query': f'ts>={int(start_time.timestamp())} AND ts<={int(end_time.timestamp())}'
        }
        resp = self._api_call('GET', '/alarms', params)
        if not resp:
            return {'count': 0, 'alarms': []}

        results = resp.get('results', []) if isinstance(resp, dict) else []
        # Defensive post-filter: match common shapes
        def is_abnormal(a: Dict) -> bool:
            t = (a.get('type') or a.get('_type') or '').lower()
            msg = (a.get('message') or '').lower()
            return ('abnormal upload' in t) or ('abnormal upload' in msg)

        abns = [a for a in results if is_abnormal(a)]
        return {'count': len(abns), 'alarms': abns[: int(limit)]}



    # ==================== DASHBOARD ====================

    def get_dashboard_summary(self) -> Dict:
        alarms = self.get_alarms(24)
        devices = self.get_devices()
        flows = self.get_flows(1)
        rules = self.get_rules()
        boxes = self.get_boxes()

        online_boxes = sum(1 for b in boxes if b.get('online'))
        total_boxes = len(boxes)

        return {
            'status': 'online' if online_boxes > 0 else 'offline',
            'boxes_online': f"{online_boxes}/{total_boxes}",
            'alarm_count': alarms['count'],
            'latest_threat': alarms['latest'],
            'devices_total': devices['total'],
            'devices_online': devices['online'],
            'flows_blocked': flows['blocked'],
            'rules_active': rules['active'],
            'last_update': datetime.now().strftime('%H:%M:%S')
        }
