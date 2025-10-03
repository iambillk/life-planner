# models/rolodex_link.py
from datetime import datetime
from models.base import db

class ContactLink(db.Model):
    """
    Association between a Rolodex Contact and any target entity.
    Example target_type: 'property', 'project_tch', 'project_personal', 'equipment', ...
    """
    __tablename__ = "contact_links"

    id = db.Column(db.Integer, primary_key=True)

    # Who
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)

    # What (polymorphic)
    target_type = db.Column(db.String(40), nullable=False)   # e.g. 'property'
    target_id   = db.Column(db.Integer, nullable=False)

    # Relationship metadata
    role       = db.Column(db.String(50))        # owner, tenant, realtor, contractor, plumber, etc.
    label      = db.Column(db.String(120))       # freeform: "Primary Owner"
    is_primary = db.Column(db.Boolean, default=False)
    notes      = db.Column(db.Text)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("contact_id", "target_type", "target_id", "role",
                            name="uq_contact_target_role"),
        db.Index("ix_contactlink_target", "target_type", "target_id"),
        db.Index("ix_contactlink_contact", "contact_id"),
    )
