# app.py - Updated with Real Estate Management + HostMon (HTML) endpoints
"""
Life Management System - Application Factory
Version: 1.3.8
Updated: 2025-10-07

CHANGELOG:
v1.3.8 (2025-10-07)
- RNA calculation restored to external-only:
  * RNA = min(Alive% of external checks)
  * External checks considered: HTTP External, DNS 1.1.1.1, DNS 8.8.8.8
  * WAN and Gateway availability are NOT included in RNA.
- Dot state in /ops/api/hostmon/status_simple now keys off RNA only.
- Kept failover detection ("On Failover WAN (...)"), gateway-row switching, and EXT jitter logic.

v1.3.7 (2025-10-07)
- Failover phrasing support and gateway selection fixes.

v1.3.6 (2025-10-06)
- External jitter parsing (Cloudflare/Google) and exposure via /ops/api/hostmon/metrics_smart.

v1.3.5 (2025-10-06)
- Hardened HostMon HTML parser (fuzzy match, robust Alive%, WAN-alive=100% when role/IP found).

v1.3.4 (2025-10-06)
- Added HTML-driven endpoints: /ops/api/hostmon/status_simple, /ops/api/hostmon/metrics_smart.

v1.3.3 (2025-10-05) ... (see previous)
"""
import os, re, time
from flask import Flask, redirect, url_for, request, jsonify
from flask_session import Session
from config import Config
from models.base import db
from datetime import datetime
from bs4 import BeautifulSoup   # pip install beautifulsoup4


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(Config)
    app.jinja_env.globals.update(abs=abs)

    # Sessions
    Session(app)

    # Database
    db.init_app(app)

    # --- Upload / data directories ---
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'equipment_profiles'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'maintenance_photos'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'property_profiles'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'property_maintenance'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'personal_project_files'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'receipts'), exist_ok=True)

    # Admin Tools upload directories
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'admin_tools'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'admin_tools', 'knowledge_base'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'admin_tools', 'tool_history'), exist_ok=True)

    # ======================================================================================
    # HostMon (HTML) — single report, parsed on demand with a tiny 30s cache
    # ======================================================================================
    HM_REPORT = os.path.join(app.root_path, "static", "hostmon", "wtr_uptime.html")
    _hm_cache = {"t": 0, "ttl": 30, "data": None}

    def _read_hm():
        """Read and parse HostMon HTML report once, cache for 30s."""
        now = time.time()
        if _hm_cache["data"] and (now - _hm_cache["t"] < _hm_cache["ttl"]):
            return _hm_cache["data"]
        if not os.path.exists(HM_REPORT):
            return None

        with open(HM_REPORT, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")

        # Report timestamp ("Generated on ...")
        gen_txt = soup.get_text(" ")
        m_gen = re.search(r"Generated on\s*([0-9/:\-\sAPMapm]+)", gen_txt)
        updated = None
        if m_gen:
            try:
                updated = datetime.strptime(m_gen.group(1).strip(), "%m/%d/%Y %I:%M:%S %p").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ---------- robust helpers ----------
        def find_row_any(*needles):
            """Return first row text that contains ALL needles (case-insensitive)."""
            lows = [n.lower() for n in needles if n]
            for tr in soup.find_all("tr"):
                txt = " ".join(tr.get_text(" ").split())
                low = txt.lower()
                if all(n in low for n in lows):
                    return txt
            return ""

        def alive_pct_from_text(txt):
            """Detect Alive% or infer 'up' from common phrases (Ok/Host is alive/HTTP 200)."""
            m = re.search(r"Alive\s+(\d+(?:\.\d+)?)\s*%", txt, re.I)
            if m:
                try:
                    return float(m.group(1))
                except:
                    pass
            low = txt.lower()
            if ("host is alive" in low) or re.search(r"\bstatus\s*[:=]?\s*ok\b", low) or re.search(r"\bok\b", low):
                return 100.0
            if (" status=200" in low) or re.search(r"\b200\s*in\s*\d+\s*ms\b", low):
                return 100.0
            return 0.0

        def avg_ms_from_text(txt):
            m = re.search(r"Avg(?:erage)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*ms", txt, re.I)
            if m:
                try:
                    return float(m.group(1))
                except:
                    pass
            m2 = re.search(r"(\d+)\s*ms", txt)
            if m2:
                try:
                    return float(m2.group(1))
                except:
                    pass
            return None

        # ---------- tolerant row lookups ----------
        # WAN state row
        row_wan = find_row_any("wan", "failover") or find_row_any("check", "wan")

        # Primary gateway rows
        row_gw_ping_p = find_row_any("ping", "up", "gateway") or find_row_any("ping up to gateway")
        row_gw_jit_p  = find_row_any("jitter", "gateway")

        # Secondary gateway rows
        row_gw_ping_s = find_row_any("ping", "secondary", "gateway") or find_row_any("ping up to secondary gateway")
        row_gw_jit_s  = find_row_any("jitter", "secondary", "gateway") or find_row_any("jitter to secondary gateway")

        # External(s)
        row_dns1 = find_row_any("dns", "1.1.1.1")
        row_dns2 = find_row_any("dns", "8.8.8.8")
        row_http = find_row_any("http", "cloudflare") or find_row_any("http", "google") or find_row_any("http", "https")

        # External jitter rows (Cloudflare + Google)
        row_jit_cf = find_row_any("jitter", "cloudflare") or find_row_any("jitter", "1.1.1.1")
        row_jit_gg = find_row_any("jitter", "google")     or find_row_any("jitter", "8.8.8.8")

        # ---------- WAN role/IP/since ----------
        doc_txt = " ".join(soup.get_text(" ").split())
        wan_role, wan_ip, wan_name, wan_since = "unknown", None, None, None

        # "On Primary WAN: <ip>"
        m_primary   = re.search(r"On\s+Primary\s+WAN:\s+(\d+\.\d+\.\d+\.\d+)", (row_wan or "") + " " + doc_txt, re.I)
        # "On Secondary WAN: <ip>"
        m_secondary = re.search(r"On\s+Secondary\s+WAN:\s+(\d+\.\d+\.\d+\.\d+)", (row_wan or "") + " " + doc_txt, re.I)
        # "On Failover WAN (Frontier DHCP): <ip>"
        m_failover  = re.search(r"On\s+Failover\s+WAN\s*\(([^)]+)\)\s*:\s*(\d+\.\d+\.\d+\.\d+)", (row_wan or "") + " " + doc_txt, re.I)

        if m_failover:
            wan_role = "secondary"
            wan_name = m_failover.group(1).strip()
            wan_ip   = m_failover.group(2)
        elif m_secondary:
            wan_role = "secondary"
            wan_ip   = m_secondary.group(1)
        elif m_primary:
            wan_role = "primary"
            wan_ip   = m_primary.group(1)

        # "Status changed at ..."
        m_since = re.search(r"Status changed at\s*([0-9/:\-\sAPMapm]+)", (row_wan or ""), re.I) or \
                  re.search(r"Status changed at\s*([0-9/:\-\sAPMapm]+)", doc_txt, re.I)
        if m_since:
            try:
                wan_since = datetime.strptime(m_since.group(1).strip(), "%m/%d/%Y %I:%M:%S %p").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                wan_since = m_since.group(1).strip()

        # Alive%: treat WAN as 100 if we positively identified a role/IP anywhere (for display only).
        wan_alive = 100.0 if wan_ip else alive_pct_from_text(row_wan or "")

        # --------- Choose the correct gateway rows based on active path (for perf chips only) ----------
        failover_active = (wan_role == "secondary")
        row_gw_ping_sel = row_gw_ping_s if failover_active and row_gw_ping_s else row_gw_ping_p
        row_gw_jit_sel  = row_gw_jit_s  if failover_active and row_gw_jit_s  else row_gw_jit_p

        gw_alive   = alive_pct_from_text(row_gw_ping_sel or row_gw_jit_sel or "")
        gw_avg     = avg_ms_from_text(row_gw_ping_sel or row_gw_jit_sel or "")

        # External availability/latency
        dns1_alive = alive_pct_from_text(row_dns1 or "")
        dns2_alive = alive_pct_from_text(row_dns2 or "")
        http_alive = alive_pct_from_text(row_http or "")
        http_avg   = avg_ms_from_text(row_http or "")

        # External jitter (ms)
        jit_cf_ms = avg_ms_from_text(row_jit_cf or "")
        jit_gg_ms = avg_ms_from_text(row_jit_gg or "")

        data = {
            "updated": updated,
            "wan": {
                "role": wan_role,          # 'primary' | 'secondary' | 'unknown'
                "name": wan_name,          # e.g., "Frontier DHCP" when present
                "ip": wan_ip,
                "since": wan_since,
                "alive": wan_alive
            },
            "gw":  { "alive": gw_alive,  "avg_ms": gw_avg },
            "dns": { "dns1_alive": dns1_alive, "dns2_alive": dns2_alive },
            "http":{ "alive": http_alive, "avg_ms": http_avg },
            "jitter": { "cf_ms": jit_cf_ms, "gg_ms": jit_gg_ms }
        }
        _hm_cache["t"] = now
        _hm_cache["data"] = data
        return data

    # ---------- RNA: external-only helpers ----------
    def _rna_external_only(hm):
        """RNA = min(Alive% of external checks). Returns [0..1]."""
        externals = []
        try:
            externals.append(hm["http"]["alive"])
        except Exception:
            pass
        try:
            externals.append(hm["dns"]["dns1_alive"])
            externals.append(hm["dns"]["dns2_alive"])
        except Exception:
            pass

        # Filter out None; if nothing present, RNA=0
        vals = [v for v in externals if isinstance(v, (int, float))]
        if not vals:
            return 0.0
        return min(vals) / 100.0

    @app.route("/ops/api/hostmon/status_simple")
    def hostmon_status_simple():
        """
        Tile data: dot state (up/degraded/down), WAN role/IP, 'since' or 'updated'.
        State uses RNA (external-only availability).
        """
        hm = _read_hm()
        if not hm:
            return jsonify({"ok": False, "error": "report not found"}), 404

        A_rna = _rna_external_only(hm)

        # Dot thresholds on RNA only
        state = "up" if A_rna >= 0.995 else ("degraded" if A_rna >= 0.98 else "down")

        return jsonify({
            "ok": True,
            "updated": hm["updated"],
            "state": state,
            "wan": {
                "role": hm["wan"]["role"],
                "name": hm["wan"].get("name"),
                "ip":   hm["wan"]["ip"],
                "since": hm["wan"]["since"]
            },
            "alive": {
                "rna": A_rna
            }
        })

    @app.route("/ops/api/hostmon/metrics_smart")
    def hostmon_metrics_smart():
        """
        Metrics for chips:
        - RNA (external-only)
        - Quality (latency-based; informative)
        - GW/EXT latency, DNS/HTTP success flags, EXT jitter
        """
        hm = _read_hm()
        if not hm:
            return jsonify({"ok": False, "error": "report not found"}), 404

        # RNA (external-only)
        A_rna = _rna_external_only(hm)

        # Quality (separate chip) from latency (bounded; informative only)
        gw_ms  = hm["gw"]["avg_ms"]
        ext_ms = hm["http"]["avg_ms"]

        def s_lat(v, target):
            if v is None: return 1.0
            k = 2.0
            try:
                return 1.0 / (1.0 + ((float(v)/target)**k))
            except Exception:
                return 1.0

        S_gw  = s_lat(gw_ms, 10.0)
        S_ext = s_lat(ext_ms, 300.0)
        quality = round(min(S_gw, S_ext), 3)

        # External jitter (combine Cloudflare + Google)
        cf = hm.get("jitter", {}).get("cf_ms")
        gg = hm.get("jitter", {}).get("gg_ms")
        if cf is not None and gg is not None:
            ext_jitter_ms = (float(cf) + float(gg)) / 2.0
        else:
            ext_jitter_ms = float(cf) if cf is not None else (float(gg) if gg is not None else None)

        return jsonify({
            "ok": True,
            "updated": hm["updated"],
            "rna_pct": round(A_rna*100.0, 3),
            "quality": quality,
            "perf": {
                "gw_ms":  gw_ms,
                "ext_ms": ext_ms,
                "dns_success": 1.0 if (hm["dns"]["dns1_alive"]>0 or hm["dns"]["dns2_alive"]>0) else 0.0,
                "http_success": 1.0 if (hm["http"]["alive"]>0) else 0.0,
                "ext_jitter_ms": ext_jitter_ms
            },
            "wan": hm["wan"]
        })
    # ======================================================================================

    # --- Context processors ---
    @app.context_processor
    def inject_datetime():
        return {'datetime': datetime}

    @app.context_processor
    def inject_librenms():
        return {
            "librenms": {
                "base_url": app.config.get("LIBRENMS_BASE_URL", "").rstrip("/"),
                "token": app.config.get("LIBRENMS_API_TOKEN"),
                "img_width": app.config.get("LIBRENMS_IMG_WIDTH", 900),
                "img_height": app.config.get("LIBRENMS_IMG_HEIGHT", 220),
                "period": app.config.get("LIBRENMS_DEFAULT_PERIOD", "-24h"),
            }
        }

    # --- Blueprints ---
    register_blueprints(app)

    # --- Root route ---
    @app.route('/')
    def index():
        return redirect(url_for('daily.index'))

    # --- DB tables ---
    with app.app_context():
        db.create_all()
        
        # Initialize SSH Logs module
        from models.ssh_logs import init_ssh_logs
        init_ssh_logs()

    return app


def register_blueprints(app):
    """Register all module blueprints"""
    from modules.daily import daily_bp
    from modules.equipment import equipment_bp
    from modules.projects import projects_bp
    from modules.persprojects import persprojects_bp
    from modules.health import health_bp
    from modules.weekly import weekly_bp
    from modules.goals import goals_bp
    from modules.todo import todo_bp
    from modules.realestate import realestate_bp
    from modules.financial import financial_bp
    from modules.rolodex import rolodex_bp
    from modules.home import home_bp
    from modules.vault import vault_bp
    from modules.tasks import tasks_bp
    from modules.network.routes import network_bp
    from modules.ops_center.routes import ops_center_bp
    from modules.admin_tools import admin_tools_bp

    app.register_blueprint(daily_bp, url_prefix='/daily')
    app.register_blueprint(equipment_bp, url_prefix='/equipment')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(persprojects_bp, url_prefix='/personal')
    app.register_blueprint(health_bp, url_prefix='/health')
    app.register_blueprint(weekly_bp, url_prefix='/weekly')
    app.register_blueprint(goals_bp, url_prefix='/goals')
    app.register_blueprint(todo_bp, url_prefix='/todo')
    app.register_blueprint(financial_bp, url_prefix='/financial')
    app.register_blueprint(rolodex_bp, url_prefix='/rolodex')
    app.register_blueprint(home_bp, url_prefix='/home')
    app.register_blueprint(vault_bp, url_prefix='/vault')
    app.register_blueprint(tasks_bp)
    app.register_blueprint(network_bp)
    app.register_blueprint(ops_center_bp)
    app.register_blueprint(admin_tools_bp, url_prefix='/admin')

    # Important: do NOT pass url_prefix again here
    app.register_blueprint(realestate_bp)


if __name__ == '__main__':
    app = create_app()
    # Bind to LAN; adjust port if you’re using a different port
    app.run(debug=True, host='0.0.0.0', port=5000)
