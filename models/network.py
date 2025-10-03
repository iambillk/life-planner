# models/network.py
from models.base import db
from datetime import datetime


class Location(db.Model):
    __tablename__ = "net_locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Subnet(db.Model):
    __tablename__ = "net_subnets"

    id = db.Column(db.Integer, primary_key=True)
    cidr = db.Column(db.String(64), nullable=False, unique=True)  # e.g., 192.168.1.0/24
    vlan_id = db.Column(db.Integer)
    purpose = db.Column(db.String(120))  # Mgmt, Storage, Servers, IoT, Guests
    gateway_ip = db.Column(db.String(64))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VLAN(db.Model):
    __tablename__ = "net_vlans"

    id = db.Column(db.Integer, primary_key=True)
    vlan_id = db.Column(db.Integer, nullable=False, unique=True)
    name = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Device(db.Model):
    __tablename__ = "net_devices"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    role = db.Column(db.String(50), nullable=False)  # NAS, switch, router, AP, server, IoT, UPS, etc.
    status = db.Column(db.String(30), default="active")  # active, retired, lab, spare

    vendor = db.Column(db.String(120))
    model = db.Column(db.String(120))
    serial = db.Column(db.String(120))

    os_name = db.Column(db.String(120))
    os_version = db.Column(db.String(120))

    location = db.Column(db.String(64))

    mgmt_ip = db.Column(db.String(64))
    mgmt_url = db.Column(db.String(255))
    credential_ref = db.Column(db.String(255))  # pointer to password-manager entry

    purchase_date = db.Column(db.Date)
    warranty_expiry = db.Column(db.Date)

    primary_subnet_id = db.Column(db.Integer, db.ForeignKey("net_subnets.id"))
    primary_subnet = db.relationship("Subnet", foreign_keys=[primary_subnet_id])

    primary_vlan_id = db.Column(db.Integer, db.ForeignKey("net_vlans.id"))
    primary_vlan = db.relationship("VLAN", foreign_keys=[primary_vlan_id])

    tags = db.Column(db.String(255))  # comma-separated tags
    notes = db.Column(db.Text)

    # integration hooks
    librenms_device_id = db.Column(db.Integer)
    unraid_host = db.Column(db.String(120))
    librenms_widgets = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Interface(db.Model):
    __tablename__ = "net_interfaces"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("net_devices.id"), nullable=False)
    device = db.relationship(
        "Device",
        backref=db.backref("interfaces", lazy="dynamic", cascade="all, delete-orphan"),
    )
    name = db.Column(db.String(64))  # eth0, igb1, ix0, vmbr0
    mac_address = db.Column(db.String(64))
    link_speed = db.Column(db.String(32))  # 1G/10G/40G
    switch_port = db.Column(db.String(64))
    notes = db.Column(db.Text)


class IPAddress(db.Model):
    __tablename__ = "net_ips"

    id = db.Column(db.Integer, primary_key=True)
    interface_id = db.Column(
        db.Integer, db.ForeignKey("net_interfaces.id"), nullable=False
    )
    interface = db.relationship(
        "Interface",
        backref=db.backref("ips", lazy="dynamic", cascade="all, delete-orphan"),
    )
    address = db.Column(db.String(64), nullable=False)
    subnet_id = db.Column(db.Integer, db.ForeignKey("net_subnets.id"))
    subnet = db.relationship("Subnet")
    is_primary = db.Column(db.Boolean, default=False)


class Service(db.Model):
    __tablename__ = "net_services"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("net_devices.id"), nullable=False)
    device = db.relationship(
        "Device",
        backref=db.backref("services", lazy="dynamic", cascade="all, delete-orphan"),
    )
    name = db.Column(db.String(120), nullable=False)  # SMB, NFS, Plex, etc.
    port = db.Column(db.Integer)
    url = db.Column(db.String(255))
    notes = db.Column(db.Text)


class Attachment(db.Model):
    __tablename__ = "net_attachments"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("net_devices.id"), nullable=False)
    device = db.relationship(
        "Device",
        backref=db.backref("attachments", lazy="dynamic", cascade="all, delete-orphan"),
    )
    title = db.Column(db.String(200), nullable=False)
    vault_doc_id = db.Column(db.Integer)  # optional link to Vault
    external_url = db.Column(db.String(255))
    notes = db.Column(db.Text)


class DeviceLink(db.Model):
    __tablename__ = "net_device_links"

    id = db.Column(db.Integer, primary_key=True)
    source_device_id = db.Column(
        db.Integer, db.ForeignKey("net_devices.id"), nullable=False
    )
    target_device_id = db.Column(
        db.Integer, db.ForeignKey("net_devices.id"), nullable=False
    )
    relation_type = db.Column(db.String(50))  # uplink, stacked, depends_on, backup_of
    notes = db.Column(db.Text)
