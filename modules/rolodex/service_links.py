# modules/rolodex/service_links.py
from typing import Optional
from models.base import db
from models.rolodex_link import ContactLink

def link_contact(contact_id: int, target_type: str, target_id: int,
                 role: Optional[str] = None, label: Optional[str] = None,
                 is_primary: bool = False, notes: Optional[str] = None) -> ContactLink:
    if is_primary and role:
        ContactLink.query.filter_by(
            target_type=target_type, target_id=target_id, role=role, is_primary=True
        ).update({"is_primary": False})
    link = ContactLink(
        contact_id=contact_id, target_type=target_type, target_id=target_id,
        role=role, label=label, is_primary=is_primary, notes=notes
    )
    db.session.add(link)
    db.session.commit()
    return link

def unlink_contact(link_id: int) -> None:
    link = ContactLink.query.get(link_id)
    if link:
        db.session.delete(link)
        db.session.commit()

def set_primary(link_id: int) -> None:
    link = ContactLink.query.get(link_id)
    if not link or not link.role:
        return
    ContactLink.query.filter_by(
        target_type=link.target_type, target_id=link.target_id, role=link.role, is_primary=True
    ).update({"is_primary": False})
    link.is_primary = True
    db.session.commit()

def links_for_target(target_type: str, target_id: int):
    return ContactLink.query.filter_by(target_type=target_type, target_id=target_id).all()

def links_for_contact(contact_id: int):
    return ContactLink.query.filter_by(contact_id=contact_id).all()
