from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from sqlalchemy import or_
from models.base import db
from models.network import Device, Subnet, VLAN  # Location removed (Option B)
from modules.network.service_librenms import (
    summarize_live_status,
    get_syslog,
    summarize_live_status_map,
    summarize_failed_services,
    summarize_failed_services_by_device,
)

network_bp = Blueprint("network", __name__, url_prefix="/network")

# ---------- helpers ----------
def _norm(s):
    return (s or "").strip()

ROLE_CHOICES = [
    "NAS", "Switch", "Router", "AP", "Server", "IoT", "UPS", "Camera",
    "Printer", "IPS", "Workstation", "Hypervisor"
]
STATUS_CHOICES = ["active", "retired", "lab", "spare"]

# Option B: static list (no DB)
LOCATION_CHOICES = [
    "Bedroom", "Closet", "Server Rack", "Upstairs Den", "Music Room",
    "Pool Room", "Garage", "Kids Game Desk", "Front Room",
    "Barn", "TCH SFJ"
]

# ---------- list (single canonical view) ----------
@network_bp.route("/", methods=["GET"])
@network_bp.route("/devices", methods=["GET"], endpoint="devices_list")
def devices_list():
    q = _norm(request.args.get("q"))
    role = _norm(request.args.get("role"))
    loc  = _norm(request.args.get("location"))  # string-based location (Option B)

    base = Device.query
    if q:
        like = f"%{q}%"
        base = base.filter(or_(
            Device.name.ilike(like),
            Device.mgmt_ip.ilike(like),
            Device.tags.ilike(like),
            Device.vendor.ilike(like),
            Device.model.ilike(like),
        ))
    if role:
        base = base.filter(Device.role == role)
    if loc:
        base = base.filter(Device.location == loc)

    devices = base.order_by(Device.name.asc()).all()

    # Service alerts summary (warnings + critical)
    try:
        svc_summary = summarize_failed_services()
    except Exception:
        svc_summary = {"total_failed": 0, "affected_devices": 0, "by_type": {}, "by_severity": {}, "items": []}

    # Initial live_map optional (JS fetches fresh)
    live_map = {}

    return render_template(
        "network/devices_list.html",
        devices=devices,
        role_choices=ROLE_CHOICES,
        locations=[],                        # legacy-safe no-op
        location_choices=LOCATION_CHOICES,   # if any UI uses it
        live_map=live_map,
        svc_summary=svc_summary,
    )

# Back-compat alias so url_for('network.devices') still works
@network_bp.route("/devices", methods=["GET"], endpoint="devices")
def _devices_alias():
    return devices_list()

# ---------- new ----------
@network_bp.route("/devices/new", methods=["GET", "POST"])
def device_new():
    if request.method == "POST":
        d = Device(
            name=_norm(request.form.get("name")),
            role=_norm(request.form.get("role") or "other"),
            status=_norm(request.form.get("status") or "active"),
            vendor=_norm(request.form.get("vendor")),
            model=_norm(request.form.get("model")),
            serial=_norm(request.form.get("serial")),
            os_name=_norm(request.form.get("os_name")),
            os_version=_norm(request.form.get("os_version")),
            location=_norm(request.form.get("location")),  # Option B: string field
            mgmt_ip=_norm(request.form.get("mgmt_ip")),
            mgmt_url=_norm(request.form.get("mgmt_url")),
            credential_ref=_norm(request.form.get("credential_ref")),
            purchase_date=request.form.get("purchase_date") or None,
            warranty_expiry=request.form.get("warranty_expiry") or None,
            primary_subnet_id=int(request.form.get("primary_subnet_id")) if request.form.get("primary_subnet_id") else None,
            primary_vlan_id=int(request.form.get("primary_vlan_id")) if request.form.get("primary_vlan_id") else None,
            tags=_norm(request.form.get("tags")),
            notes=_norm(request.form.get("notes")),
        )

        widgets = request.form.getlist("widgets")
        d.librenms_widgets = ",".join(widgets) if widgets else None

        if not d.name:
            flash("Name is required.", "warning")
            return render_template(
                "network/device_form.html",
                mode="new",
                device=None,
                subnets=Subnet.query.all(),
                vlans=VLAN.query.all(),
                role_choices=ROLE_CHOICES,
                status_choices=STATUS_CHOICES,
                location_choices=LOCATION_CHOICES,
            )

        db.session.add(d)
        db.session.commit()
        flash("Device added.", "success")
        return redirect(url_for("network.device_detail", id=d.id))

    return render_template(
        "network/device_form.html",
        mode="new",
        device=None,
        subnets=Subnet.query.all(),
        vlans=VLAN.query.all(),
        role_choices=ROLE_CHOICES,
        status_choices=STATUS_CHOICES,
        location_choices=LOCATION_CHOICES,
    )

# ---------- detail ----------
@network_bp.route("/devices/<int:id>")
def device_detail(id):
    d = Device.query.get_or_404(id)
    live = summarize_live_status(d.librenms_device_id)

    syslog_entries = []
    if d.librenms_widgets and "syslog" in d.librenms_widgets.split(","):
        syslog_entries = get_syslog(d.librenms_device_id, limit=50)

    return render_template(
        "network/device_detail.html",
        d=d,
        live=live,
        syslog_entries=syslog_entries
    )

# ---------- edit ----------
@network_bp.route("/devices/<int:id>/edit", methods=["GET", "POST"])
def device_edit(id):
    d = Device.query.get_or_404(id)

    if request.method == "POST":
        d.name = _norm(request.form.get("name"))
        d.role = _norm(request.form.get("role") or d.role)
        d.status = _norm(request.form.get("status") or d.status)
        d.vendor = _norm(request.form.get("vendor"))
        d.model = _norm(request.form.get("model"))
        d.serial = _norm(request.form.get("serial"))
        d.os_name = _norm(request.form.get("os_name"))
        d.os_version = _norm(request.form.get("os_version"))
        d.location = _norm(request.form.get("location"))
        d.mgmt_ip = _norm(request.form.get("mgmt_ip"))
        d.mgmt_url = _norm(request.form.get("mgmt_url"))
        d.credential_ref = _norm(request.form.get("credential_ref"))
        d.purchase_date = request.form.get("purchase_date") or None
        d.warranty_expiry = request.form.get("warranty_expiry") or None
        d.primary_subnet_id = int(request.form.get("primary_subnet_id")) if request.form.get("primary_subnet_id") else None
        d.primary_vlan_id = int(request.form.get("primary_vlan_id")) if request.form.get("primary_vlan_id") else None
        d.tags = _norm(request.form.get("tags"))
        d.notes = _norm(request.form.get("notes"))

        l_id = _norm(request.form.get("librenms_device_id"))
        d.librenms_device_id = int(l_id) if l_id else None
        d.unraid_host = _norm(request.form.get("unraid_host"))

        widgets = request.form.getlist("widgets")
        d.librenms_widgets = ",".join(widgets) if widgets else None

        if not d.name:
            flash("Name is required.", "warning")
            return render_template(
                "network/device_form.html",
                mode="edit",
                device=d,
                subnets=Subnet.query.all(),
                vlans=VLAN.query.all(),
                role_choices=ROLE_CHOICES,
                status_choices=STATUS_CHOICES,
                location_choices=LOCATION_CHOICES,
            )

        db.session.commit()
        flash("Device updated.", "success")
        return redirect(url_for("network.device_detail", id=d.id))

    return render_template(
        "network/device_form.html",
        mode="edit",
        device=d,
        subnets=Subnet.query.all(),
        vlans=VLAN.query.all(),
        role_choices=ROLE_CHOICES,
        status_choices=STATUS_CHOICES,
        location_choices=LOCATION_CHOICES,
    )

# ---------- live status API (for device list) ----------

@network_bp.route("/api/services/failed_map")
def api_services_failed_map():
    return jsonify(summarize_failed_services_by_device())


@network_bp.get("/api/live-status")
def api_live_status():
    ids_param = (request.args.get("ids") or "").strip()
    if not ids_param:
        return jsonify({})
    try:
        id_list = [int(x) for x in ids_param.split(",") if x.isdigit()]
    except Exception:
        return jsonify({})

    devices = Device.query.filter(Device.id.in_(id_list)).all()
    out = {}
    for d in devices:
        state = "unknown"
        uptime_seconds = None
        uptime_human = None
        try:
            if d.librenms_device_id:
                info = summarize_live_status(d.librenms_device_id) or {}
                cand = (info.get("overall") or info.get("status") or
                        info.get("availability") or info.get("state"))
                if isinstance(cand, bool):
                    state = "up" if cand else "down"
                elif isinstance(cand, int):
                    state = "up" if cand == 1 else "down"
                elif isinstance(cand, str):
                    s = cand.lower()
                    state = "up" if s in ("up", "ok", "1", "available") else (
                        "down" if s in ("down", "0", "critical", "unavailable") else "unknown"
                    )
                uptime_seconds = info.get("uptime_seconds")
                uptime_human = info.get("uptime_human")
        except Exception:
            state = "unknown"

        out[d.id] = {
            "status": state,
            "uptime_seconds": uptime_seconds,
            "uptime_human": uptime_human,
        }
    return jsonify(out)

# ---------- services JSON for UI (warnings + critical) ----------
@network_bp.route("/api/services/failed")
def api_services_failed():
    return jsonify(summarize_failed_services())

# ---------- raw + debug helpers ----------
@network_bp.route("/services/down")
def services_down():
    summary = summarize_failed_services()
    return jsonify(summary)

@network_bp.route("/debug/librenms/services_raw")
def debug_librenms_services_raw():
    from modules.network.service_librenms import _get  # reuse the client
    out = {}
    try:
        out["state_2"] = _get("/services?state=2", nocache=True)
    except Exception as e:
        out["state_2_error"] = str(e)
    try:
        out["state_1"] = _get("/services?state=1", nocache=True)
    except Exception as e:
        out["state_1_error"] = str(e)
    try:
        out["all"] = _get("/services", nocache=True)
    except Exception as e:
        out["all_error"] = str(e)
    return out, 200

# ---------- any-down endpoint (RESTORED) ----------
@network_bp.route("/api/any-down", methods=["GET"], endpoint="api_any_down")
def api_any_down():
    # Get only devices that are linked to LibreNMS
    lnms_ids = [
        lid for (lid,) in db.session.query(Device.librenms_device_id)
        .filter(Device.librenms_device_id.isnot(None))
        .all()
        if lid
    ]
    if not lnms_ids:
        return jsonify({"any_down": False, "down_count": 0})

    # Use the batch helper to get true availability per LibreNMS device id
    live_map = summarize_live_status_map(lnms_ids)  # { lnms_id: 'up' | 'down' | 'unknown' }
    down = sum(1 for s in (live_map or {}).values() if s == "down")
    return jsonify({"any_down": down > 0, "down_count": down})

# ---------- delete ----------
@network_bp.route("/devices/<int:id>/delete", methods=["POST"])
def device_delete(id):
    d = Device.query.get_or_404(id)
    device_name = d.name
    try:
        db.session.delete(d)
        db.session.commit()
        flash(f"Device '{device_name}' has been deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting device: {str(e)}", "danger")
        return redirect(url_for("network.device_detail", id=id))
    return redirect(url_for("network.devices_list"))

# ---------- subnet management ----------
@network_bp.route("/subnets")
def subnets():
    subnets = Subnet.query.order_by(Subnet.cidr).all()
    return render_template("network/subnets.html", subnets=subnets)

@network_bp.route("/subnets/new", methods=["GET", "POST"])
def subnet_new():
    if request.method == "POST":
        s = Subnet(
            cidr=_norm(request.form.get("cidr")),
            purpose=_norm(request.form.get("purpose")),
            gateway=_norm(request.form.get("gateway")),
            dns_servers=_norm(request.form.get("dns_servers")),
            notes=_norm(request.form.get("notes")),
        )
        if not s.cidr:
            flash("CIDR is required.", "warning")
            return render_template("network/subnet_form.html", subnet=None)

        db.session.add(s)
        db.session.commit()
        flash(f"Subnet {s.cidr} added.", "success")
        return redirect(url_for("network.subnets"))

    return render_template("network/subnet_form.html", subnet=None)

@network_bp.route("/subnets/<int:id>/delete", methods=["POST"])
def subnet_delete(id):
    s = Subnet.query.get_or_404(id)
    cidr = s.cidr
    try:
        db.session.delete(s)
        db.session.commit()
        flash(f"Subnet {cidr} deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting subnet: {str(e)}", "danger")
    return redirect(url_for("network.subnets"))

# ---------- vlan management ----------
@network_bp.route("/vlans")
def vlans():
    vlans = VLAN.query.order_by(VLAN.vlan_id).all()
    return render_template("network/vlans.html", vlans=vlans)

@network_bp.route("/vlans/new", methods=["GET", "POST"])
def vlan_new():
    if request.method == "POST":
        v = VLAN(
            vlan_id=int(request.form.get("vlan_id")) if request.form.get("vlan_id") else None,
            name=_norm(request.form.get("name")),
            purpose=_norm(request.form.get("purpose")),
            subnet_cidr=_norm(request.form.get("subnet_cidr")),
            notes=_norm(request.form.get("notes")),
        )
        if not v.vlan_id:
            flash("VLAN ID is required.", "warning")
            return render_template("network/vlan_form.html", vlan=None)

        db.session.add(v)
        db.session.commit()
        flash(f"VLAN {v.vlan_id} added.", "success")
        return redirect(url_for("network.vlans"))

    return render_template("network/vlan_form.html", vlan=None)

@network_bp.route("/vlans/<int:id>/delete", methods=["POST"])
def vlan_delete(id):
    v = VLAN.query.get_or_404(id)
    vlan_id = v.vlan_id
    try:
        db.session.delete(v)
        db.session.commit()
        flash(f"VLAN {vlan_id} deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting VLAN: {str(e)}", "danger")
    return redirect(url_for("network.vlans"))
