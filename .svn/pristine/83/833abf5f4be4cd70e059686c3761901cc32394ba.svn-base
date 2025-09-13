from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import or_, func
from datetime import datetime
from . import rolodex_bp
from models import db, Contact, Company

# ---------- helpers ----------
def _norm(s: str | None) -> str:
    return (s or '').strip()

def _company_choices():
    return Company.query.filter_by(archived=False).order_by(Company.name.asc()).all()

def _parse_tags(raw: str | None) -> str:
    # store as normalized "tag1, tag2" (single spaces after commas, trimmed)
    if not raw:
        return ''
    parts = [p.strip() for p in raw.split(',')]
    parts = [p for p in parts if p]
    return ', '.join(dict.fromkeys(parts))  # dedupe, keep order

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
    companies_map = {}
    if paginated.items:
        # fetch companies in one go to avoid N+1 in template
        cids = {c.company_id for c in paginated.items if c.company_id}
        if cids:
            for c in Company.query.filter(Company.id.in_(cids)).all():
                companies_map[c.id] = c

    return render_template('rolodex/contacts_list.html',
                           contacts=paginated,
                           q=q, sort=sort, show_archived=show_archived,
                           companies_map=companies_map)

# ---------- contacts: detail ----------
@rolodex_bp.route('/contacts/<int:id>')
def contact_detail(id):
    contact = Contact.query.get_or_404(id)
    return render_template('rolodex/contact_detail.html', contact=contact)

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

        c = Contact(
            first_name=first,
            last_name=last,
            display_name=display,
            title=_norm(request.form.get('title')),
            email=email or None,
            phone=phone or None,
            company_id=int(request.form.get('company_id')) if request.form.get('company_id') else None,
            tags=_parse_tags(request.form.get('tags')),
            notes=_norm(request.form.get('notes')),
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

        c.title = _norm(request.form.get('title'))
        c.email = email or None
        c.phone = phone or None
        c.company_id = int(request.form.get('company_id')) if request.form.get('company_id') else None
        c.tags = _parse_tags(request.form.get('tags'))
        c.notes = _norm(request.form.get('notes'))
        c.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Contact updated.', 'success')
        return redirect(url_for('rolodex.contact_detail', id=c.id))
    companies = _company_choices()
    return render_template('rolodex/contact_form.html', mode='edit', companies=companies, contact=c, form=c.__dict__)

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
    return render_template('rolodex/company_detail.html', company=company)

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

        co = Company(
            name=name,
            website=website or None,
            phone=_norm(request.form.get('phone')),
            tags=_parse_tags(request.form.get('tags')),
            notes=_norm(request.form.get('notes')),
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

        co.name = name
        co.website = website or None
        co.phone = _norm(request.form.get('phone'))
        co.tags = _parse_tags(request.form.get('tags'))
        co.notes = _norm(request.form.get('notes'))
        co.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Company updated.', 'success')
        return redirect(url_for('rolodex.company_detail', id=co.id))
    return render_template('rolodex/company_form.html', mode='edit', company=co, form=co.__dict__)

@rolodex_bp.route('/companies/<int:id>/archive', methods=['POST'])
def company_archive(id):
    co = Company.query.get_or_404(id)
    co.archived = not co.archived
    db.session.commit()
    flash('Company archived.' if co.archived else 'Company unarchived.', 'success')
    return redirect(url_for('rolodex.company_detail', id=co.id))

@rolodex_bp.route('/companies/<int:id>/delete', methods=['POST'])
def company_delete(id):
    co = Company.query.get_or_404(id)
    db.session.delete(co)
    db.session.commit()
    flash('Company deleted.', 'success')
    return redirect(url_for('rolodex.companies'))
