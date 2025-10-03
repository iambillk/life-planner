# models/company_link.py
from datetime import datetime
from models.base import db

class CompanyLink(db.Model):
    """Link a Rolodex Company to any target entity (e.g., property)."""
    __tablename__ = "company_links"

    id = db.Column(db.Integer, primary_key=True)

    # Subject
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    # Target (polymorphic)
    target_type = db.Column(db.String(40), nullable=False)   # e.g. 'property'
    target_id   = db.Column(db.Integer, nullable=False)

    # Relationship metadata
    role       = db.Column(db.String(50))        # vendor, hvac, landscaping, lender, etc.
    label      = db.Column(db.String(120))       # freeform e.g., "Primary HVAC Vendor"
    is_primary = db.Column(db.Boolean, default=False)
    notes      = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("company_id", "target_type", "target_id", "role",
                            name="uq_company_target_role"),
        db.Index("ix_companylink_target", "target_type", "target_id"),
        db.Index("ix_companylink_company", "company_id"),
    )
