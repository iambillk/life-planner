# modules/rolodex/routes.py — imports

from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import or_, func
from datetime import datetime
from werkzeug.utils import secure_filename
import os

from . import rolodex_bp

# ✅ Use the same pattern as the rest of the app
from models.base import db
from models.rolodex import Contact, Company
from models.realestate import Property
from models.rolodex_link import ContactLink          # people↔property links
from models.company_link import CompanyLink           # company↔property links

# Import flow (VCF/CSV)
from .routes_import import *  # registers /rolodex/import and /rolodex/import/commit

# Link services (people + companies)
from modules.rolodex.service_links import (
    link_contact, unlink_contact, set_primary, links_for_contact, links_for_target
)
from modules.rolodex.service_company_links import (
    link_company, unlink_company as unlink_company_link, set_company_primary, company_links_for_target
)

# Convert Contact → Company
from modules.rolodex.service_convert import convert_contact_to_company


# ---------- helpers ----------

def _contact_property_links(contact_id: int):
    links = ContactLink.query.filter_by(contact_id=contact_id, target_type="property").all()
    prop_ids = [l.target_id for l in links] or []
    props_by_id = {p.id: p for p in Property.query.filter(Property.id.in_(prop_ids)).all()} if prop_ids else {}
    # order: role asc, primary first, then property name
    links.sort(key=lambda l: ((l.role or "~"), -int(bool(l.is_primary)), props_by_id.get(l.target_id).name if props_by_id.get(l.target_id) else ""))
    return links, props_by_id

def _company_property_links(company_id: int):
    links = CompanyLink.query.filter_by(company_id=company_id, target_type="property").all()
    prop_ids = [l.target_id for l in links] or []
    props_by_id = {p.id: p for p in Property.query.filter(Property.id.in_(prop_ids)).all()} if prop_ids else {}
    links.sort(key=lambda l: ((l.role or "~"), -int(bool(l.is_primary)), props_by_id.get(l.target_id).name if props_by_id.get(l.target_id) else ""))
    return links, props_by_id



def _norm(s: str | None) -> str:
    return (s or '').strip()

def _allowed_file(filename):
    """Check if file extension is allowed for photos"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _company_choices():
    return Company.query.filter_by(archived=False).order_by(Company.name.asc()).all()

def _parse_tags(raw: str | None) -> str:
    # store as normalized "tag1, tag2" (single spaces after commas, trimmed)
    if not raw:
        return ''
    parts = [p.strip() for p in raw.split(',')]
    parts = [p for p in parts if p]
    return ', '.join(dict.fromkeys(parts))  # dedupe, keep order

def _parse_date(date_string: str | None):
    """Parse date string to date object"""
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except:
        return None

# ---------- index / tabs ----------
@rolodex_bp.route('/')
def index():
    return redirect(url_for('rolodex.contacts'))

# ---------- contacts: list ----------
@rolodex_bp.route('/contacts')
def contacts():
    q = _norm(request.args.get('q'))
    sort = request.args.get('sort', 'name_asc')
    show_archived = request.args.get('archived') == '1'
    page = int(request.args.get('page', 1))
    per_page = 25

    base = Contact.query
    if not show_archived:
        base = base.filter(Contact.archived.is_(False))

    if q:
        like = f"%{q}%"
        base = (base
                .outerjoin(Company, Contact.company_id == Company.id)
                .filter(or_(
                    Contact.display_name.ilike(like),
                    Contact.first_name.ilike(like),
                    Contact.last_name.ilike(like),
                    Contact.email.ilike(like),
                    Contact.phone.ilike(like),
                    Contact.tags.ilike(like),
                    Company.name.ilike(like)
                )))

    if sort == 'name_desc':
        base = base.order_by(Contact.display_name.desc())
    elif sort == 'updated_desc':
        base = base.order_by(Contact.updated_at.desc().nullslast())
    else:
        base = base.order_by(Contact.display_name.asc())

    paginated = base.paginate(page=page, per_page=per_page, error_out=False)

    # Keep this for resolving company names for items on the current page
    companies_map = {}
    if paginated.items:
        cids = {c.company_id for c in paginated.items if c.company_id}
        if cids:
            for c in Company.query.filter(Company.id.in_(cids)).all():
                companies_map[c.id] = c

    # ✅ NEW: real company counts (use whichever you want on the card)
    total_companies_active = Company.query.filter(Company.archived.is_(False)).count()
    total_companies_all = Company.query.count()

    return render_template(
        'rolodex/contacts_list.html',
        contacts=paginated,
        q=q, sort=sort, show_archived=show_archived,
        companies_map=companies_map,
        # expose both so the template can pick:
        total_companies_active=total_companies_active,
        total_companies_all=total_companies_all
    )


# ---------- contacts: detail ----------
@rolodex_bp.route("/contacts/<int:id>")
def contact_detail(id):
    contact = Contact.query.get_or_404(id)

    # NEW: load linked properties for this contact
    prop_links, properties_by_id = _contact_property_links(id)

    return render_template(
        "rolodex/contact_detail.html",
        contact=contact,
        property_links=prop_links,
        properties_by_id=properties_by_id,
    )

# ---------- contacts: new/edit ----------
@rolodex_bp.route('/contacts/new', methods=['GET', 'POST'])
def contact_new():
    if request.method == 'POST':
        first = _norm(request.form.get('first_name'))
        last = _norm(request.form.get('last_name'))
        display = _norm(request.form.get('display_name') or f"{first} {last}".strip() or 'New Contact')
        email = _norm(request.form.get('email'))
        phone = _norm(request.form.get('phone'))
        
        # dedupe warn
        dup = None
        if email:
            dup = Contact.query.filter(Contact.email.ilike(email)).first() or dup
        if not dup and phone:
            dup = Contact.query.filter(Contact.phone.ilike(phone)).first()
        if dup and request.form.get('dedupe_override') != '1':
            flash(f'Looks like this email/phone is used by "{dup.display_name}". Click save again to confirm.', 'warning')
            companies = _company_choices()
            return render_template('rolodex/contact_form.html', mode='new', companies=companies, form=request.form, dedupe=True)

        # Handle profile photo upload
        profile_photo_filename = None
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename and _allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{timestamp}{ext}"
                upload_path = os.path.join('static', 'contact_photos')
                os.makedirs(upload_path, exist_ok=True)
                file.save(os.path.join(upload_path, filename))
                profile_photo_filename = filename

        # Handle business card photo
        business_card_filename = None
        if 'business_card_photo' in request.files:
            file = request.files['business_card_photo']
            if file and file.filename and _allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                filename = f"card_{name}_{timestamp}{ext}"
                upload_path = os.path.join('static', 'contact_photos')
                os.makedirs(upload_path, exist_ok=True)
                file.save(os.path.join(upload_path, filename))
                business_card_filename = filename

        c = Contact(
            # Basic info
            first_name=first,
            last_name=last,
            display_name=display,
            title=_norm(request.form.get('title')),
            email=email or None,
            phone=phone or None,
            company_id=int(request.form.get('company_id')) if request.form.get('company_id') else None,
            tags=_parse_tags(request.form.get('tags')),
            notes=_norm(request.form.get('notes')),
            profile_photo=profile_photo_filename,
            business_card_photo=business_card_filename,
            
            # Address
            street_address=_norm(request.form.get('street_address')) or None,
            address_line_2=_norm(request.form.get('address_line_2')) or None,
            city=_norm(request.form.get('city')) or None,
            state=_norm(request.form.get('state')) or None,
            zip_code=_norm(request.form.get('zip_code')) or None,
            country=_norm(request.form.get('country')) or None,
            
            # Additional phones/contact
            mobile_phone=_norm(request.form.get('mobile_phone')) or None,
            work_phone=_norm(request.form.get('work_phone')) or None,
            home_phone=_norm(request.form.get('home_phone')) or None,
            personal_email=_norm(request.form.get('personal_email')) or None,
            website=_norm(request.form.get('website')) or None,
            
            # Social
            linkedin_url=_norm(request.form.get('linkedin_url')) or None,
            twitter_url=_norm(request.form.get('twitter_url')) or None,
            facebook_url=_norm(request.form.get('facebook_url')) or None,
            instagram_url=_norm(request.form.get('instagram_url')) or None,
            github_url=_norm(request.form.get('github_url')) or None,
            
            # Dates
            birthday=_parse_date(request.form.get('birthday')),
            anniversary=_parse_date(request.form.get('anniversary')),
            
            # Personal
            spouse_name=_norm(request.form.get('spouse_name')) or None,
            children_names=_norm(request.form.get('children_names')) or None,
            assistant_name=_norm(request.form.get('assistant_name')) or None
        )
        db.session.add(c)
        db.session.commit()
        flash('Contact saved.', 'success')
        return redirect(url_for('rolodex.contact_detail', id=c.id))
        
    companies = _company_choices()
    return render_template('rolodex/contact_form.html', mode='new', companies=companies, form={})

@rolodex_bp.route('/contacts/<int:id>/edit', methods=['GET', 'POST'])
def contact_edit(id):
    c = Contact.query.get_or_404(id)
    if request.method == 'POST':
        first = _norm(request.form.get('first_name'))
        last = _norm(request.form.get('last_name'))
        c.first_name = first
        c.last_name = last
        c.display_name = _norm(request.form.get('display_name') or f"{first} {last}".strip() or c.display_name)
        email = _norm(request.form.get('email'))
        phone = _norm(request.form.get('phone'))
        
        # dedupe warn (exclude self)
        dup = None
        if email:
            dup = Contact.query.filter(Contact.id != c.id, Contact.email.ilike(email)).first() or dup
        if not dup and phone:
            dup = Contact.query.filter(Contact.id != c.id, Contact.phone.ilike(phone)).first()
        if dup and request.form.get('dedupe_override') != '1':
            flash(f'Email/phone already used by "{dup.display_name}". Click save again to confirm.', 'warning')
            companies = _company_choices()
            return render_template('rolodex/contact_form.html', mode='edit', companies=companies, form=request.form, contact=c, dedupe=True)

        # Handle profile photo upload
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename and _allowed_file(file.filename):
                # Delete old photo if exists
                if c.profile_photo:
                    old_path = os.path.join('static', 'contact_photos', c.profile_photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Save new photo
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{timestamp}{ext}"
                upload_path = os.path.join('static', 'contact_photos')
                os.makedirs(upload_path, exist_ok=True)
                file.save(os.path.join(upload_path, filename))
                c.profile_photo = filename

        # Handle business card photo
        if 'business_card_photo' in request.files:
            file = request.files['business_card_photo']
            if file and file.filename and _allowed_file(file.filename):
                # Delete old card if exists
                if c.business_card_photo:
                    old_path = os.path.join('static', 'contact_photos', c.business_card_photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Save new card
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(filename)
                filename = f"card_{name}_{timestamp}{ext}"
                upload_path = os.path.join('static', 'contact_photos')
                os.makedirs(upload_path, exist_ok=True)
                file.save(os.path.join(upload_path, filename))
                c.business_card_photo = filename

        # Update all fields
        c.title = _norm(request.form.get('title'))
        c.email = email or None
        c.phone = phone or None
        c.company_id = int(request.form.get('company_id')) if request.form.get('company_id') else None
        c.tags = _parse_tags(request.form.get('tags'))
        c.notes = _norm(request.form.get('notes'))
        
        # Address
        c.street_address = _norm(request.form.get('street_address')) or None
        c.address_line_2 = _norm(request.form.get('address_line_2')) or None
        c.city = _norm(request.form.get('city')) or None
        c.state = _norm(request.form.get('state')) or None
        c.zip_code = _norm(request.form.get('zip_code')) or None
        c.country = _norm(request.form.get('country')) or None
        
        # Additional phones/contact
        c.mobile_phone = _norm(request.form.get('mobile_phone')) or None
        c.work_phone = _norm(request.form.get('work_phone')) or None
        c.home_phone = _norm(request.form.get('home_phone')) or None
        c.personal_email = _norm(request.form.get('personal_email')) or None
        c.website = _norm(request.form.get('website')) or None
        
        # Social
        c.linkedin_url = _norm(request.form.get('linkedin_url')) or None
        c.twitter_url = _norm(request.form.get('twitter_url')) or None
        c.facebook_url = _norm(request.form.get('facebook_url')) or None
        c.instagram_url = _norm(request.form.get('instagram_url')) or None
        c.github_url = _norm(request.form.get('github_url')) or None
        
        # Dates
        c.birthday = _parse_date(request.form.get('birthday'))
        c.anniversary = _parse_date(request.form.get('anniversary'))
        
        # Personal
        c.spouse_name = _norm(request.form.get('spouse_name')) or None
        c.children_names = _norm(request.form.get('children_names')) or None
        c.assistant_name = _norm(request.form.get('assistant_name')) or None
        
        c.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Contact updated.', 'success')
        return redirect(url_for('rolodex.contact_detail', id=c.id))
        
    companies = _company_choices()
    # Convert None values to empty strings for form display
    form_data = {k: (v if v is not None else '') for k, v in c.__dict__.items()}
    return render_template('rolodex/contact_form.html', mode='edit', companies=companies, contact=c, form=form_data)

@rolodex_bp.route('/contacts/<int:id>/archive', methods=['POST'])
def contact_archive(id):
    c = Contact.query.get_or_404(id)
    c.archived = not c.archived
    db.session.commit()
    flash('Contact archived.' if c.archived else 'Contact unarchived.', 'success')
    return redirect(url_for('rolodex.contact_detail', id=c.id))

@rolodex_bp.route('/contacts/<int:id>/delete', methods=['POST'])
def contact_delete(id):
    c = Contact.query.get_or_404(id)
    
    # Delete photos if they exist
    if c.profile_photo:
        photo_path = os.path.join('static', 'contact_photos', c.profile_photo)
        if os.path.exists(photo_path):
            os.remove(photo_path)
    
    if c.business_card_photo:
        card_path = os.path.join('static', 'contact_photos', c.business_card_photo)
        if os.path.exists(card_path):
            os.remove(card_path)
    
    db.session.delete(c)
    db.session.commit()
    flash('Contact deleted.', 'success')
    return redirect(url_for('rolodex.contacts'))

# ---------- companies: list/detail/crud ----------
@rolodex_bp.route('/companies')
def companies():
    q = _norm(request.args.get('q'))
    sort = request.args.get('sort', 'name_asc')
    show_archived = request.args.get('archived') == '1'
    page = int(request.args.get('page', 1))
    per_page = 25

    base = Company.query
    if not show_archived:
        base = base.filter(Company.archived.is_(False))
    if q:
        like = f"%{q}%"
        base = base.filter(or_(
            Company.name.ilike(like),
            Company.website.ilike(like),
            Company.phone.ilike(like),
            Company.tags.ilike(like)
        ))
    if sort == 'updated_desc':
        base = base.order_by(Company.updated_at.desc().nullslast())
    elif sort == 'name_desc':
        base = base.order_by(Company.name.desc())
    else:
        base = base.order_by(Company.name.asc())

    paginated = base.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('rolodex/companies_list.html',
                           companies=paginated, q=q, sort=sort, show_archived=show_archived)

@rolodex_bp.route('/companies/<int:id>')
def company_detail(id):
    company = Company.query.get_or_404(id)

    # Load linked properties for this company
    property_links, properties_by_id = _company_property_links(id)

    return render_template(
        'rolodex/company_detail.html',
        company=company,
        property_links=property_links,
        properties_by_id=properties_by_id,
    )


@rolodex_bp.route('/companies/new', methods=['GET', 'POST'])
def company_new():
    if request.method == 'POST':
        name = _norm(request.form.get('name'))
        website = _norm(request.form.get('website'))
        # simple dedupe: name or domain (lowercased)
        dup = Company.query.filter(func.lower(Company.name) == func.lower(name)).first()
        if (dup or (website and Company.query.filter(func.lower(Company.website) == func.lower(website)).first())) \
           and request.form.get('dedupe_override') != '1':
            flash('Company may already exist. Click save again to confirm.', 'warning')
            return render_template('rolodex/company_form.html', mode='new', form=request.form, dedupe=True)

        # Handle logo upload
        logo_filename = None
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and _allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name_part, ext = os.path.splitext(filename)
                filename = f"logo_{name_part}_{timestamp}{ext}"
                upload_path = os.path.join('static', 'company_logos')
                os.makedirs(upload_path, exist_ok=True)
                file.save(os.path.join(upload_path, filename))
                logo_filename = filename

        co = Company(
            name=name,
            website=website or None,
            phone=_norm(request.form.get('phone')),
            tags=_parse_tags(request.form.get('tags')),
            notes=_norm(request.form.get('notes')),
            logo=logo_filename,
            industry=_norm(request.form.get('industry')) or None,
            size=_norm(request.form.get('size')) or None,
            address=_norm(request.form.get('address')) or None,
            linkedin=_norm(request.form.get('linkedin')) or None,
            twitter=_norm(request.form.get('twitter')) or None,
        )
        db.session.add(co)
        db.session.commit()
        flash('Company saved.', 'success')
        return redirect(url_for('rolodex.company_detail', id=co.id))
    return render_template('rolodex/company_form.html', mode='new', form={})

@rolodex_bp.route('/companies/<int:id>/edit', methods=['GET', 'POST'])
def company_edit(id):
    co = Company.query.get_or_404(id)
    if request.method == 'POST':
        name = _norm(request.form.get('name'))
        website = _norm(request.form.get('website'))
        # dedupe excluding self
        dup_name = Company.query.filter(Company.id != co.id, func.lower(Company.name) == func.lower(name)).first()
        dup_site = website and Company.query.filter(Company.id != co.id, func.lower(Company.website) == func.lower(website)).first()
        if (dup_name or dup_site) and request.form.get('dedupe_override') != '1':
            flash('Name/website already used by another company. Click save again to confirm.', 'warning')
            return render_template('rolodex/company_form.html', mode='edit', form=request.form, company=co, dedupe=True)

        # Handle logo upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and _allowed_file(file.filename):
                # Delete old logo if exists
                if co.logo:
                    old_path = os.path.join('static', 'company_logos', co.logo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Save new logo
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name_part, ext = os.path.splitext(filename)
                filename = f"logo_{name_part}_{timestamp}{ext}"
                upload_path = os.path.join('static', 'company_logos')
                os.makedirs(upload_path, exist_ok=True)
                file.save(os.path.join(upload_path, filename))
                co.logo = filename

        co.name = name
        co.website = website or None
        co.phone = _norm(request.form.get('phone'))
        co.tags = _parse_tags(request.form.get('tags'))
        co.notes = _norm(request.form.get('notes'))
        co.industry = _norm(request.form.get('industry')) or None
        co.size = _norm(request.form.get('size')) or None
        co.address = _norm(request.form.get('address')) or None
        co.linkedin = _norm(request.form.get('linkedin')) or None
        co.twitter = _norm(request.form.get('twitter')) or None
        co.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Company updated.', 'success')
        return redirect(url_for('rolodex.company_detail', id=co.id))
    
    # Convert None values to empty strings for form display
    form_data = {k: (v if v is not None else '') for k, v in co.__dict__.items()}
    return render_template('rolodex/company_form.html', mode='edit', company=co, form=form_data)

@rolodex_bp.route('/companies/<int:id>/archive', methods=['POST'])
def company_archive(id):
    co = Company.query.get_or_404(id)
    co.archived = not co.archived
    db.session.commit()
    flash('Company archived.' if co.archived else 'Company unarchive.', 'success')
    return redirect(url_for('rolodex.company_detail', id=co.id))

@rolodex_bp.route('/companies/<int:id>/delete', methods=['POST'])
def company_delete(id):
    co = Company.query.get_or_404(id)
    
    # Delete logo if it exists
    if co.logo:
        logo_path = os.path.join('static', 'company_logos', co.logo)
        if os.path.exists(logo_path):
            os.remove(logo_path)
    
    db.session.delete(co)
    db.session.commit()
    flash('Company deleted.', 'success')
    return redirect(url_for('rolodex.companies'))

# imports near the top
from flask import request, redirect, url_for, flash
from modules.rolodex.service_convert import convert_contact_to_company
from models.rolodex import Contact, Company

# ... your existing routes ...

@rolodex_bp.route("/contacts/<int:id>/convert-to-company", methods=["POST"])
def contact_convert_to_company(id):
    try:
        move_links = bool(request.form.get("move_links", "1"))  # default: move links
        company, created = convert_contact_to_company(id, move_links=move_links)
        msg = f"Converted to company '{company.name}'." if created else f"Merged into existing company '{company.name}'."
        flash(msg, "success")
        return redirect(url_for("rolodex.company_detail", id=company.id))
    except Exception as e:
        flash(f"Conversion failed: {e}", "error")
        return redirect(url_for("rolodex.contact_edit", id=id))


@rolodex_bp.route("/contacts/<int:id>/link/property", methods=["GET", "POST"])
def contact_link_property(id):
    contact = Contact.query.get_or_404(id)
    if request.method == "POST":
        property_id = int(request.form["property_id"])
        role  = (request.form.get("role") or "").strip() or None
        label = (request.form.get("label") or "").strip() or None
        is_primary = bool(request.form.get("is_primary"))
        notes = (request.form.get("notes") or "").strip() or None
        link_contact(contact_id=id, target_type="property", target_id=property_id,
                     role=role, label=label, is_primary=is_primary, notes=notes)
        flash("Linked to property.", "success")
        return redirect(url_for("rolodex.contact_detail", id=id))
    props = Property.query.order_by(Property.name.asc()).all()
    return render_template("rolodex/contact_link_property.html", contact=contact, properties=props)

@rolodex_bp.route("/contacts/<int:id>/link/<int:link_id>/primary", methods=["POST"])
def contact_make_primary(id, link_id):
    set_primary(link_id)
    flash("Primary updated.", "success")
    return redirect(url_for("rolodex.contact_detail", id=id))

@rolodex_bp.route("/contacts/<int:id>/link/<int:link_id>/remove", methods=["POST"])
def contact_unlink_property(id, link_id):
    unlink_contact(link_id)
    flash("Link removed.", "success")
    return redirect(url_for("rolodex.contact_detail", id=id))

@rolodex_bp.route("/companies/<int:id>/link/property", methods=["GET", "POST"])
def company_link_property(id):
    company = Company.query.get_or_404(id)
    if request.method == "POST":
        property_id = int(request.form["property_id"])
        role  = (request.form.get("role") or "").strip() or None
        label = (request.form.get("label") or "").strip() or None
        is_primary = bool(request.form.get("is_primary"))
        notes = (request.form.get("notes") or "").strip() or None
        link_company(company_id=id, target_type="property", target_id=property_id,
                     role=role, label=label, is_primary=is_primary, notes=notes)
        flash("Linked to property.", "success")
        return redirect(url_for("rolodex.company_detail", id=id))
    props = Property.query.order_by(Property.name.asc()).all()
    return render_template("rolodex/company_link_property.html", company=company, properties=props)

@rolodex_bp.route("/companies/<int:id>/link/<int:link_id>/primary", methods=["POST"])
def company_make_primary(id, link_id):
    set_company_primary(link_id)
    flash("Primary updated.", "success")
    return redirect(url_for("rolodex.company_detail", id=id))

@rolodex_bp.route("/companies/<int:id>/link/<int:link_id>/remove", methods=["POST"])
def company_unlink_property(id, link_id):
    unlink_company_link(link_id)
    flash("Link removed.", "success")
    return redirect(url_for("rolodex.company_detail", id=id))
