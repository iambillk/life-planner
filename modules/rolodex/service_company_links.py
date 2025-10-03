# modules/rolodex/service_company_links.py
from typing import Optional
from models.base import db
from models.company_link import CompanyLink

def link_company(
    company_id: int,
    target_type: str,
    target_id: int,
    role: Optional[str] = None,
    label: Optional[str] = None,
    is_primary: bool = False,
    notes: Optional[str] = None,
) -> CompanyLink:
    if is_primary and role:
        CompanyLink.query.filter_by(
            target_type=target_type, target_id=target_id, role=role, is_primary=True
        ).update({"is_primary": False})
    link = CompanyLink(
        company_id=company_id, target_type=target_type, target_id=target_id,
        role=role, label=label, is_primary=is_primary, notes=notes
    )
    db.session.add(link)
    db.session.commit()
    return link

def set_company_primary(link_id: int) -> None:
    link = CompanyLink.query.get(link_id)
    if not link or not link.role:
        return
    CompanyLink.query.filter_by(
        target_type=link.target_type, target_id=link.target_id, role=link.role, is_primary=True
    ).update({"is_primary": False})
    link.is_primary = True
    db.session.commit()

def unlink_company(link_id: int) -> None:
    link = CompanyLink.query.get(link_id)
    if link:
        db.session.delete(link)
        db.session.commit()

def company_links_for_target(target_type: str, target_id: int):
    return CompanyLink.query.filter_by(target_type=target_type, target_id=target_id).all()
