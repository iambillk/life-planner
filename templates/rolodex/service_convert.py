# modules/rolodex/service_convert.py
from datetime import datetime
from typing import Optional, Tuple

from models.base import db
from models.rolodex import Contact, Company
from models.rolodex_link import ContactLink
from models.company_link import CompanyLink

def _get_or_create_company_by_name(name: str) -> Tuple[Company, bool]:
    co = Company.query.filter(Company.name.ilike(name)).first()
    created = False
    if not co:
        co = Company(name=name)
        db.session.add(co)
        db.session.flush()
        created = True
    return co, created

def convert_contact_to_company(contact_id: int, move_links: bool = True) -> Tuple[Company, bool]:
    """
    Convert a contact into a company. Returns (company, created_bool).

    Steps:
    1) Company.name = contact.first_name (required)
       - If a company with that name already exists (case-insensitive), merge into it.
    2) If move_links: migrate ContactLink(property) -> CompanyLink(property)
    3) Archive the contact (archived=True)
    """
    contact = Contact.query.get(contact_id)
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")

    name = (contact.first_name or "").strip()
    if not name:
        raise ValueError("Cannot convert: contact.first_name is empty (company name required).")

    # 1) get/create company
    co, created = _get_or_create_company_by_name(name)

    # Optionally copy a couple of handy fields if company was created now
    if created:
        if contact.phone and not co.phone:
            co.phone = contact.phone
        if contact.website and not co.website:
            co.website = contact.website
        # keep provenance in notes
        stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        note_line = f"[Converted from Contact #{contact.id} on {stamp}]"
        co.notes = (co.notes + ("\n" if co.notes else "") + note_line) if co.notes else note_line

    # 2) move property links (ContactLink -> CompanyLink)
    if move_links:
        links = ContactLink.query.filter_by(contact_id=contact.id, target_type="property").all()
        for l in links:
            # prevent duplicate same-role links to the same target for this company
            exists = CompanyLink.query.filter_by(
                company_id=co.id,
                target_type=l.target_type,
                target_id=l.target_id,
                role=l.role,
            ).first()
            if not exists:
                new_l = CompanyLink(
                    company_id=co.id,
                    target_type=l.target_type,
                    target_id=l.target_id,
                    role=l.role,
                    label=l.label,
                    is_primary=l.is_primary,
                    notes=l.notes,
                )
                db.session.add(new_l)
            db.session.delete(l)

    # 3) archive contact
    contact.archived = True
    db.session.commit()
    return co, created
