"""
Operations Command Center - Routes
Version: 1.3.0
Last Modified: 2025-10-04
Author: Billas + Marcus

Description:
- Unified routes restoring MikroTik switch integration and DLI PDU controls.
- Defensive getters so the page still renders even if a backend is missing.

File: /modules/ops_center/routes.py
"""

from __future__ import annotations

from flask import Blueprint, render_template, jsonify, request, current_app
from datetime import datetime

# ---- Integrations (import paths based on your tree) ---------------------------
# LibreNMS
try:
    from modules.ops_center.integrations import OpsLibreNMS
except Exception:
    OpsLibreNMS = None  # type: ignore

# MikroTik
try:
    from modules.ops_center.mikrotik import MikroTikAPI
except Exception:
    MikroTikAPI = None  # type: ignore

# DLI PDU (single-file helper path you showed)
try:
    from modules.ops_center.dli_pdu import DLIPduAPI
except Exception:
    DLIPduAPI = None  # type: ignore

# Firewalla
try:
    from modules.ops_center.firewalla import FirewallaAPI
except Exception:
    FirewallaAPI = None  # type: ignore

# Create blueprint with url_prefix
ops_center_bp = Blueprint("ops_center", __name__, url_prefix="/ops")


# ==============================================================================
# Dashboard
# ==============================================================================
@ops_center_bp.route("/")
def dashboard():
    """
    Main dashboard view for Operations Command Center.
    Always provides safe 'pdu' values so Jinja never crashes.
    """

    # ---------------- LibreNMS (best-effort) -----------------------------------
    device_stats = {}
    wan_stats = {}
    alert_summary = {}
    graph_urls = {}
    ips_alerts = {}
    if OpsLibreNMS:
        try:
            nms = OpsLibreNMS()
            device_stats = _safe(nms, "get_device_stats", {}) or {}
            wan_stats = _safe(nms, "get_port_bandwidth", {}) or {}
            alert_summary = _safe(nms, "get_alert_summary", {}) or {}
            graph_urls = _safe(nms, "get_port_graphs", {}) or {}
            ips_alerts = _safe(nms, "get_ips_alerts", {}) or {}

            # --- Build a 3-line timestamped summary for IPS (like Firewalla) ---
            ips_latest_str = "No Alerts"
            try:
                recent = ips_alerts.get("recent_alerts", [])
                lines, seen = [], set()
                from datetime import datetime

                for a in recent[:8]:
                    msg = (a.get("rule") or a.get("message") or a.get("alert") or "").strip()
                    if not msg:
                        continue

                    # timestamp may be epoch or string
                    ts = a.get("ts") or a.get("timestamp") or a.get("time")
                    ts_str = ""
                    try:
                        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
                            ts_str = datetime.fromtimestamp(int(ts)).strftime("%H:%M")
                        elif isinstance(ts, str) and len(ts) >= 5:
                            try:
                                ts_str = datetime.fromisoformat(ts.replace("Z", "")).strftime("%H:%M")
                            except Exception:
                                ts_str = ts[11:16] if len(ts) >= 16 else ""
                    except Exception:
                        ts_str = ""

                    line = f"[{ts_str}] {msg}" if ts_str else msg
                    line = (line[:80] + "...") if len(line) > 80 else line

                    key = f"{ts_str}|{msg}"
                    if key in seen:
                        continue
                    seen.add(key)
                    lines.append(line)

                    if len(lines) == 3:
                        break

                if lines:
                    ips_latest_str = "\n\n".join(lines)

            except Exception as e:
                print(f"[IPS] summary build failed: {e}")
                ips_latest_str = "No Alerts"

        except Exception:
            pass

    # ---------------- MikroTik (best-effort) -----------------------------------
    switch_ports = []
    switch_stats = {"total_ports": 0, "ports_up": 0, "ports_down": 0, "ports_errors": 0}
    if MikroTikAPI:
        try:
            mt = MikroTikAPI()
            switch_ports = _safe(mt, "get_all_ports", []) or []
            switch_stats = {
                "total_ports": len(switch_ports),
                "ports_up": sum(1 for p in switch_ports if p.get("status") == "up"),
                "ports_down": sum(1 for p in switch_ports if p.get("status") == "down"),
                "ports_errors": sum(1 for p in switch_ports if p.get("has_errors")),
            }
        except Exception:
            pass

    # ---------------- PDU (safe defaults + best-effort real values) ------------
    pdu_context = {
        "name": current_app.config.get("DLI_PDU_NAME", "DLI-PDU-1"),
        "current_amps": 0.0,
        "max_amps": 15,
        "voltage": 120.0,  # change to 208.0 if applicable
        "watts": 0.0,
        "outlets": [],
    }
    if DLIPduAPI:
        try:
            pdu = DLIPduAPI()

            # Power metrics
            power = _first_ok(
                pdu,
                [("get_power_status", {}), ("get_metrics", {}), ("status", {}), ("get_status", {})],
            )
            power = power or {}
            volts = _num(power.get("voltage", power.get("volts", pdu_context["voltage"])))
            amps = _num(power.get("current_amps", power.get("amps", pdu_context["current_amps"])))
            maxa = int(power.get("max_amps", pdu_context["max_amps"]))
            watts = power.get("watts")
            if watts is None:
                watts = volts * amps

            # Outlets
            outlets = _first_ok(
                pdu,
                [("get_all_outlets", []), ("list_outlets", []), ("get_outlets", []), ("outlets", [])],
            ) or []

            pdu_context.update(
                {
                    "current_amps": amps,
                    "max_amps": maxa,
                    "voltage": volts,
                    "watts": float(_num(watts)),
                    "outlets": [
                        {
                            "id": (o.get("number") if isinstance(o, dict) else None) or o.get("id", 0),
                            "name": (o.get("name") if isinstance(o, dict) else None) or "Outlet",
                            "state": o.get("physical_state", o.get("state", False)),
                            "locked": o.get("locked", False),
                        }
                        for o in outlets
                        if isinstance(o, dict)
                    ],
                }
            )
        except Exception:
            # keep defaults
            pass

    # ---------------- Firewalla (best-effort) -----------------------------------
    fw_alarms = {"count": 0, "latest": "No Alerts"}
    fw_devices = {"total": 0, "online": 0, "offline": 0}
    fw_summary = {
        "status": "offline",
        "boxes_online": "0/0",
        "flows_blocked": 0,
        "rules_active": 0
    }
    if FirewallaAPI:
        try:
            fw = FirewallaAPI()
            fw_alarms = _safe(fw, "get_alarms", {"count": 0, "latest": "No Alerts"}, 24) or {"count": 0, "latest": "No Alerts"}
            fw_devices = _safe(fw, "get_devices", {"total": 0, "online": 0, "offline": 0}) or {"total": 0, "online": 0, "offline": 0}
            fw_summary = _safe(fw, "get_dashboard_summary", {
                "status": "offline",
                "boxes_online": "0/0", 
                "flows_blocked": 0,
                "rules_active": 0
            }) or {
                "status": "offline",
                "boxes_online": "0/0",
                "flows_blocked": 0,
                "rules_active": 0
            }
            
            # --- Combine top 3 latest alarms (with timestamps + spacing) for dashboard display ---
            if fw_alarms and isinstance(fw_alarms.get("alarms"), list):
                alarms_list = fw_alarms.get("alarms", [])
                msgs = []
                seen = set()

                for a in alarms_list[:8]:  # scan a few deep in case of dupes
                    msg = a.get("message") or a.get("type") or ""
                    if not msg:
                        continue

                    # --- timestamp formatting (Firewalla 'ts' is UNIX seconds) ---
                    ts = a.get("ts") or a.get("timestamp")
                    try:
                        from datetime import datetime
                        ts_str = datetime.fromtimestamp(int(ts)).strftime("%H:%M") if ts else ""
                    except Exception:
                        ts_str = ""

                    # --- build formatted line ---
                    line = f"[{ts_str}] {msg.strip()}" if ts_str else msg.strip()

                    # trim overly long lines
                    line = (line[:80] + "...") if len(line) > 80 else line

                    # create unique key: same message + same timestamp = duplicate
                    dedupe_key = f"{ts_str}|{msg.strip()}"
                    if dedupe_key not in seen:
                        seen.add(dedupe_key)
                        msgs.append(line)

                    if len(msgs) == 3:
                        break

                # join with double newline for spacing between alerts
                if len(msgs) >= 2:
                    fw_alarms["latest"] = "\n\n".join(msgs)
                elif len(msgs) == 1:
                    fw_alarms["latest"] = msgs[0]


  
        except Exception as e:
            pass

    # ---------------- Context for template -------------------------------------
    context = {
        "page_title": "Operations Command Center",
        "last_refresh": datetime.now().strftime("%H:%M:%S"),
        "system_status": device_stats.get("status"),
        "wan1": wan_stats.get("wan1", {}),
        "wan2": wan_stats.get("wan2", {}),
        "wan1_graph_url": graph_urls.get("wan1_graph"),
        "wan2_graph_url": graph_urls.get("wan2_graph"),
        "alerts": {
            "ips_count": ips_alerts.get("count", 0),
            "ips_latest": ips_latest_str,
            "firewalla_count": fw_alarms.get("count", 0),
            "firewalla_latest": fw_alarms.get("latest", "No Alerts"),
            "syslogs_count": alert_summary.get("warning"),
            "hostmon_downtime": "4min @3am",  # placeholder
        },
        "pdu": pdu_context,
        "firewalla": {
            "status": fw_summary.get("status", "offline"),
            "boxes_online": fw_summary.get("boxes_online", "0/0"),
            "devices_total": fw_devices.get("total", 0),
            "devices_online": fw_devices.get("online", 0),
            "flows_blocked": fw_summary.get("flows_blocked", 0),
            "rules_active": fw_summary.get("rules_active", 0)
        },
        "switches": [
            {"name": "MikroTik", "ports": 24, "active": 18},
            {"name": "Zyxel-1", "ports": 48, "active": 42},
            {"name": "Zyxel-2", "ports": 24, "active": 20},
        ],
        "mikrotik_switch": {
            "model": "CRS354-48G-4S+2Q+",
            "ports": switch_ports,
            "stats": switch_stats,
        },
        "device_stats": device_stats,
    }

    # Render; if the template is missing during dev, return JSON so you can inspect
    try:
        return render_template("ops_center/dashboard.html", **context)
    except Exception:
        return jsonify(context)


# ==============================================================================
# Refresh API (AJAX)
# ==============================================================================
@ops_center_bp.route("/api/refresh")
def api_refresh():
    """
    Lightweight metrics for periodic refresh (AJAX).
    """
    # LibreNMS
    wan_stats = {}
    ips_alerts = {}
    if OpsLibreNMS:
        try:
            nms = OpsLibreNMS()
            wan_stats = _safe(nms, "get_port_bandwidth", {}) or {}
            ips_alerts = _safe(nms, "get_ips_alerts", {}) or {}

            # --- Build a 3-line timestamped summary for IPS (like Firewalla) ---
            ips_latest_str = ips_alerts.get("latest") or ""
            try:
                recent = ips_alerts.get("recent_alerts", [])
                lines, seen = [], set()

                from datetime import datetime

                for a in recent[:8]:  # look a few deep to skip dupes
                    # message text (prefer explicit rule/message)
                    msg = (a.get("rule") or a.get("message") or a.get("alert") or "").strip()
                    if not msg:
                        continue

                    # tolerant timestamp parsing
                    ts = a.get("ts") or a.get("timestamp") or a.get("time")  # may be epoch or string
                    ts_str = ""
                    try:
                        if isinstance(ts, (int, float,)) or (isinstance(ts, str) and ts.isdigit()):
                            ts_str = datetime.fromtimestamp(int(ts)).strftime("%H:%M")
                        elif isinstance(ts, str) and len(ts) >= 5:
                            # try simple slice (HH:MM) as a safe fallback
                            # or tighten if your format is known
                            try:
                                ts_str = datetime.fromisoformat(ts.replace("Z","")).strftime("%H:%M")
                            except Exception:
                                ts_str = ts[11:16] if len(ts) >= 16 else ""
                    except Exception:
                        ts_str = ""

                    line = f"[{ts_str}] {msg}" if ts_str else msg
                    line = (line[:80] + "...") if len(line) > 80 else line

                    # dedupe only if both timestamp & message are identical
                    key = f"{ts_str}|{msg}"
                    if key in seen:
                        continue
                    seen.add(key)

                    lines.append(line)
                    if len(lines) == 3:
                        break

                if lines:
                    # double newline = blank line between alerts
                    ips_latest_str = "\n\n".join(lines)
            except Exception:
                pass

        except Exception:
            pass

    # MikroTik quick stats
    ports = []
    if MikroTikAPI:
        try:
            mt = MikroTikAPI()
            ports = _safe(mt, "get_all_ports", []) or []
        except Exception:
            pass
    switch_stats = {
        "ports_up": sum(1 for p in ports if p.get("status") == "up"),
        "total_ports": len(ports),
    }

    # PDU amps
    pdu_amps = 0.0
    if DLIPduAPI:
        try:
            pdu = DLIPduAPI()
            power = _first_ok(
                pdu,
                [("get_power_status", {}), ("get_metrics", {}), ("status", {}), ("get_status", {})],
            ) or {}
            pdu_amps = _num(power.get("current_amps", power.get("amps", 0.0)))
        except Exception:
            pass

    # Firewalla
    fw_alarms = {"count": 0, "latest": "No Alerts"}
    if FirewallaAPI:
        try:
            fw = FirewallaAPI()
            fw_alarms = _safe(fw, "get_alarms", {"count": 0, "latest": "No Alerts"}, 1) or {"count": 0, "latest": "No Alerts"}
        except Exception:
            pass

    return jsonify(
        {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "wan1_down": _nested(wan_stats, ["wan1", "download_mbps"]),
            "wan1_up": _nested(wan_stats, ["wan1", "upload_mbps"]),
            "wan2_down": _nested(wan_stats, ["wan2", "download_mbps"]),
            "wan2_up": _nested(wan_stats, ["wan2", "upload_mbps"]),
            "ips_count": ips_alerts.get("count", 0),
            "firewalla_count": fw_alarms.get("count", 0),
            "firewalla_latest": fw_alarms.get("latest", "No Alerts"),
            "pdu_amps": pdu_amps,
            "switch_ports_up": switch_stats["ports_up"],
            "switch_total_ports": switch_stats["total_ports"],
        }
    )


# ==============================================================================
# PDU Control Endpoints
# ==============================================================================
@ops_center_bp.route("/api/pdu/outlets/all", methods=["GET"])
def api_pdu_outlets_all():
    try:
        if not DLIPduAPI:
            return jsonify({"success": False, "error": "PDU backend unavailable"}), 501
        pdu = DLIPduAPI()
        outlets = _safe(pdu, "get_all_outlets", []) or []
        power = _first_ok(
            pdu, [("get_power_status", {}), ("get_metrics", {}), ("status", {}), ("get_status", {})]
        )
        return jsonify(
            {
                "success": True,
                "outlets": [
                    {
                        "id": o.get("number"),
                        "name": o.get("name"),
                        "state": o.get("physical_state", o.get("state")),
                        "locked": o.get("locked", False),
                    }
                    for o in outlets
                    if isinstance(o, dict)
                ],
                "power": power,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ops_center_bp.route("/api/pdu/outlet/<int:outlet_id>/toggle", methods=["POST"])
def api_pdu_outlet_toggle(outlet_id: int):
    try:
        if not DLIPduAPI:
            return jsonify({"success": False, "error": "PDU backend unavailable"}), 501
        pdu = DLIPduAPI()

        # Convert human-friendly 1..N to 0-based if needed by your helper
        api_outlet_id = outlet_id - 1

        outlet = _safe(pdu, "get_outlet_status", None, api_outlet_id)
        if not outlet:
            return jsonify({"success": False, "error": "Outlet not found"}), 404
        if outlet.get("locked", False):
            return jsonify({"success": False, "error": "Outlet is locked"}), 403

        new_state = not bool(outlet.get("physical_state", outlet.get("state", False)))
        ok = _safe(pdu, "set_outlet_state", False, api_outlet_id, new_state)
        if ok:
            return jsonify({"success": True, "outlet_id": outlet_id, "new_state": "on" if new_state else "off"})
        return jsonify({"success": False, "error": "Failed to toggle outlet"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ops_center_bp.route("/api/pdu/outlet/<int:outlet_id>/cycle", methods=["POST"])
def api_pdu_outlet_cycle(outlet_id: int):
    try:
        if not DLIPduAPI:
            return jsonify({"success": False, "error": "PDU backend unavailable"}), 501
        pdu = DLIPduAPI()
        api_outlet_id = outlet_id - 1
        delay = request.json.get("delay") if request.is_json else None
        if _safe(pdu, "cycle_outlet", False, api_outlet_id, delay):
            return jsonify({"success": True, "outlet_id": outlet_id, "message": f"Outlet {outlet_id} cycling..."})
        return jsonify({"success": False, "error": "Failed to cycle outlet"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ops_center_bp.route("/api/pdu/outlet/<int:outlet_id>/name", methods=["POST"])
def api_pdu_outlet_rename(outlet_id: int):
    try:
        if not DLIPduAPI:
            return jsonify({"success": False, "error": "PDU backend unavailable"}), 501
        if not request.is_json or "name" not in request.json:
            return jsonify({"success": False, "error": "Name required"}), 400

        new_name = (request.json.get("name") or "").strip()
        if not new_name:
            return jsonify({"success": False, "error": "Name required"}), 400

        pdu = DLIPduAPI()
        api_outlet_id = outlet_id - 1
        ok = _safe(pdu, "set_outlet_name", False, api_outlet_id, new_name)
        if ok:
            return jsonify({"success": True, "outlet_id": outlet_id, "new_name": new_name})
        return jsonify({"success": False, "error": "Failed to rename outlet"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================================
# MikroTik Port Endpoints
# ==============================================================================
@ops_center_bp.route("/api/switch/port/<int:port_id>")
def api_switch_port_details(port_id: int):
    if not MikroTikAPI:
        return jsonify({"error": "MikroTik backend unavailable"}), 501
    try:
        mt = MikroTikAPI()
        # support either method name
        detail = _safe(mt, "get_port_details", None, port_id) or _safe(mt, "get_port_detail", None, port_id)
        if not detail:
            return jsonify({"error": "Port not found"}), 404
        # If your helper returns bps, derive mbps
        if "rx_rate_bps" in detail:
            detail["rx_mbps"] = round(detail.get("rx_rate_bps", 0) / 1_000_000, 2)
        if "tx_rate_bps" in detail:
            detail["tx_mbps"] = round(detail.get("tx_rate_bps", 0) / 1_000_000, 2)
        return jsonify(detail)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ops_center_bp.route("/api/switch/port/<int:port_id>/toggle", methods=["POST"])
def api_switch_port_toggle(port_id: int):
    if not MikroTikAPI:
        return jsonify({"success": False, "error": "MikroTik backend unavailable"}), 501
    try:
        mt = MikroTikAPI()
        detail = _safe(mt, "get_port_details", None, port_id) or _safe(mt, "get_port_detail", None, port_id)
        if not detail:
            return jsonify({"success": False, "error": "Port not found"}), 404
        new_state = not bool(detail.get("enabled", True))
        ok = _safe(mt, "toggle_port", None, port_id, new_state)
        if ok is None:  # if your helper uses a different name:
            ok = _safe(mt, "set_port_enabled", False, port_id, new_state)
        return jsonify({"success": bool(ok), "port_id": port_id, "new_state": "enabled" if new_state else "disabled"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ops_center_bp.route("/api/switch/port/<int:port_id>/name", methods=["POST"])
def api_switch_port_rename(port_id: int):
    if not MikroTikAPI:
        return jsonify({"success": False, "error": "MikroTik backend unavailable"}), 501
    try:
        if not request.is_json or "name" not in request.json:
            return jsonify({"success": False, "error": "Name required"}), 400
        new_name = (request.json.get("name") or "").strip()
        if not new_name:
            return jsonify({"success": False, "error": "Name required"}), 400

        mt = MikroTikAPI()
        ok = _safe(mt, "set_port_name", False, port_id, new_name)
        return jsonify({"success": bool(ok), "port_id": port_id, "new_name": new_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================================
# IPS Details & WHOIS
# ==============================================================================
@ops_center_bp.route("/api/ips-details")
def api_ips_details():
    if not OpsLibreNMS:
        return jsonify({"error": "LibreNMS backend unavailable"}), 501
    try:
        nms = OpsLibreNMS()
        ips_data = _safe(nms, "get_ips_alerts", {}) or {}
        return jsonify(
            {
                "count": ips_data.get("count", 0),
                "alerts": ips_data.get("recent_alerts", []),
                "analytics": ips_data.get("analytics", {}),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


# ==============================================================================
# Firewalla API Endpoints
# ==============================================================================
@ops_center_bp.route("/api/firewalla/details")
def api_firewalla_details():
    """Get detailed Firewalla security information."""
    if not FirewallaAPI:
        return jsonify({"success": False, "error": "Firewalla backend unavailable"}), 501
    try:
        fw = FirewallaAPI()
        alarms = _safe(fw, "get_alarms", {}, 24) or {}
        devices = _safe(fw, "get_devices", {}) or {}
        flows = _safe(fw, "get_flows", {}, 72) or {}
        rules = _safe(fw, "get_rules", {}) or {}
        boxes = _safe(fw, "get_boxes", []) or []
        
        return jsonify({
            "success": True,
            "alarms": {
                "count": alarms.get("count", 0),
                "latest": alarms.get("latest", "No Alerts"),
                "recent": alarms.get("alarms", [])[:100]
            },
            "devices": devices,
            "flows": flows,
            "rules": rules,
            "boxes": boxes,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ops_center_bp.route("/api/firewalla/alarms/<int:hours>")
def api_firewalla_alarms(hours: int):
    """Get Firewalla alarms for specific time period."""
    if not FirewallaAPI:
        return jsonify({"success": False, "error": "Firewalla backend unavailable"}), 501
    if hours < 1 or hours > 168:
        return jsonify({"success": False, "error": "Hours must be between 1 and 168"}), 400
    try:
        fw = FirewallaAPI()
        alarms = _safe(fw, "get_alarms", {}, hours) or {}
        return jsonify({
            "success": True,
            "hours": hours,
            "alarms": alarms,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Target List – list current targets
@ops_center_bp.route("/api/firewalla/targets", methods=["GET"])
def api_fw_targets_list():
    if not FirewallaAPI:
        return jsonify({"success": False, "error": "Firewalla backend unavailable"}), 501
    try:
        fw = FirewallaAPI()
        tl = fw.get_target_list() or {}
        return jsonify({"success": True, "id": tl.get("id"), "name": tl.get("name"), "targets": tl.get("targets", [])})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Target List – add target
@ops_center_bp.route("/api/firewalla/targets", methods=["POST"])
def api_fw_targets_add():
    if not FirewallaAPI:
        return jsonify({"success": False, "error": "Firewalla backend unavailable"}), 501
    try:
        if not request.is_json or "target" not in request.json:
            return jsonify({"success": False, "error": "Missing 'target'"}), 400
        target = (request.json.get("target") or "").strip()
        if not target:
            return jsonify({"success": False, "error": "Empty target"}), 400
        fw = FirewallaAPI()
        ok = fw.add_block_target(target)
        return jsonify({"success": bool(ok), "target": target})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Target List – remove target
@ops_center_bp.route("/api/firewalla/targets/<path:target>", methods=["DELETE"])
def api_fw_targets_remove(target: str):
    if not FirewallaAPI:
        return jsonify({"success": False, "error": "Firewalla backend unavailable"}), 501
    try:
        target = (target or "").strip()
        if not target:
            return jsonify({"success": False, "error": "Empty target"}), 400
        fw = FirewallaAPI()
        ok = fw.remove_block_target(target)
        return jsonify({"success": bool(ok), "target": target})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ops_center_bp.route("/api/firewalla/abnormal")
def api_firewalla_abnormal():
    """Get 'Abnormal Upload' alarms for a recent window."""
    if not FirewallaAPI:
        return jsonify({"success": False, "error": "Firewalla backend unavailable"}), 501
    try:
        hours = int(request.args.get("hours", 24))
        limit = int(request.args.get("limit", 100))
        fw = FirewallaAPI()
        data = fw.get_abnormal_upload_alarms(hours=hours, limit=limit)
        return jsonify({"success": True, "hours": hours, "count": data["count"], "alarms": data["alarms"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# ==============================================================================
# Helpers
# ==============================================================================
def _safe(obj, method: str, default, *args, **kwargs):
    """Call obj.method(*args, **kwargs) if it exists; otherwise return default."""
    try:
        fn = getattr(obj, method, None)
        if callable(fn):
            return fn(*args, **kwargs)
    except Exception:
        return default
    return default


def _first_ok(obj, methods):
    """Given [(name, default)], call the first that works; else return None/defaults."""
    for name, default in methods:
        try:
            fn = getattr(obj, name, None)
            if callable(fn):
                val = fn()
                if val is not None:
                    return val
                return default
        except Exception:
            continue
    return None


def _num(x, fallback=0.0):
    """Safely convert to float."""
    try:
        return float(x)
    except Exception:
        return float(fallback)


def _nested(d, path):
    """Safely get nested dict values; returns None if missing."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur
