# modules/realestate/routes.py
# Real Estate routes — with outbuildings + vendors + purchase fields + delete property
from flask import render_template, request, redirect, url_for, flash, current_app
from datetime import datetime, timedelta
from collections import defaultdict
from flask import jsonify
import json
import os

# ✅ Import db and models directly from their modules (no models/__init__.py exports needed)
from models.base import db
from models.realestate import (
    Property,
    PropertyMaintenance,
    PropertyMaintenancePhoto,
    PropertyVendor,
    PropertyOutbuilding,
)

from . import realestate_bp
from modules.equipment.utils import allowed_file, save_uploaded_photo


# ---------------- Dashboard ----------------

@realestate_bp.route("/")
def dashboard():
    q = request.args.get("q", "").strip()
    query = Property.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Property.name.ilike(like),
                Property.address.ilike(like),
                Property.city.ilike(like),
                Property.state.ilike(like),
                Property.zip_code.ilike(like),
            )
        )
    properties = query.order_by(Property.name.asc()).all()
    
    # Calculate portfolio maintenance totals
    current_year = datetime.now().year
    total_ytd = 0
    total_last_year = 0
    
    for prop in properties:
        maintenance = PropertyMaintenance.query.filter_by(property_id=prop.id).all()
        for m in maintenance:
            if m.date_completed and m.cost:
                if m.date_completed.year == current_year:
                    total_ytd += m.cost
                elif m.date_completed.year == (current_year - 1):
                    total_last_year += m.cost
    
    return render_template(
        "realestate/dashboard.html",
        properties=properties,
        q=q,
        total_ytd=total_ytd,
        total_last_year=total_last_year,
        current_year=current_year,
        active="realestate",
    )


# ---------------- Property Detail ----------------

@realestate_bp.route("/<int:id>")
def property_detail(id):
    prop = Property.query.get_or_404(id)
    
    # Maintenance list
    maintenance = (
        PropertyMaintenance.query.filter_by(property_id=id)
        .order_by(
            PropertyMaintenance.date_completed.desc(),
            PropertyMaintenance.id.desc()
        )
        .all()
    )
    
    # Calculate property-specific maintenance totals
    current_year = datetime.now().year
    property_ytd = 0
    property_last_year = 0
    
    for m in maintenance:
        if m.date_completed and m.cost:
            if m.date_completed.year == current_year:
                property_ytd += m.cost
            elif m.date_completed.year == (current_year - 1):
                property_last_year += m.cost
    
    # Photos grouped by maintenance_id
    maint_ids = [m.id for m in maintenance] or [0]
    photos = (
        PropertyMaintenancePhoto.query
        .filter(PropertyMaintenancePhoto.maintenance_id.in_(maint_ids))
        .order_by(
            PropertyMaintenancePhoto.uploaded_at.desc(),
            PropertyMaintenancePhoto.id.desc()
        )
        .all()
    )
    photos_by_maint = defaultdict(list)
    for ph in photos:
        photos_by_maint[ph.maintenance_id].append(ph)
    recent_photos = photos[:12]
    
    # Vendors
    vendors = (
        PropertyVendor.query.filter_by(property_id=id)
        .order_by(PropertyVendor.service_type.asc(), PropertyVendor.company_name.asc())
        .all()
    )
    
    # Outbuildings
    outbuildings = (
        PropertyOutbuilding.query.filter_by(property_id=id)
        .order_by(PropertyOutbuilding.name.asc())
        .all()
    )
    
    return render_template(
        "realestate/property_detail.html",
        property=prop,
        maintenance=maintenance,
        photos_by_maint=photos_by_maint,
        recent_photos=recent_photos,
        vendors=vendors,
        outbuildings=outbuildings,
        property_ytd=property_ytd,
        property_last_year=property_last_year,
        current_year=current_year,
        active="realestate",
    )


# ---------------- Add / Edit / Delete Property ----------------

@realestate_bp.route("/add", methods=["GET", "POST"])
def add_property():
    if request.method == "POST":
        name = request.form.get("name")

        # optional purchase date
        pd_raw = (request.form.get("purchase_date") or "").strip()
        purchase_date = None
        if pd_raw:
            try:
                purchase_date = datetime.strptime(pd_raw, "%Y-%m-%d").date()
            except ValueError:
                purchase_date = None

        prop = Property(
            name=name,
            address=request.form.get("address"),
            city=request.form.get("city"),
            state=request.form.get("state"),
            zip_code=request.form.get("zip_code"),
            country=request.form.get("country"),
            county=request.form.get("county"),
            township=request.form.get("township"),
            property_type=request.form.get("property_type"),
            year_built=request.form.get("year_built", type=int),
            square_footage=request.form.get("square_footage", type=int),
            lot_size_acres=request.form.get("lot_size_acres", type=float),
            purchase_date=purchase_date,
            purchase_price=request.form.get("purchase_price", type=float),
            notes=request.form.get("notes"),
        )

        # optional profile photo
        file = request.files.get("profile_photo")
        if file and allowed_file(file.filename):
            filename = save_uploaded_photo(file, "property_profiles", name or "property")
            prop.profile_photo = filename

        db.session.add(prop)
        db.session.commit()
        flash(f'Property "{prop.name}" added successfully!', "success")
        return redirect(url_for("realestate.property_detail", id=prop.id))

    return render_template("realestate/property_form.html", property=None, active="realestate")


@realestate_bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit_property(id):
    prop = Property.query.get_or_404(id)

    if request.method == "POST":
        prop.name = request.form.get("name")
        prop.address = request.form.get("address")
        prop.city = request.form.get("city")
        prop.state = request.form.get("state")
        prop.zip_code = request.form.get("zip_code")
        prop.country = request.form.get("country")
        prop.county = request.form.get("county")
        prop.township = request.form.get("township")
        prop.property_type = request.form.get("property_type")
        prop.year_built = request.form.get("year_built", type=int)
        prop.square_footage = request.form.get("square_footage", type=int)
        prop.lot_size_acres = request.form.get("lot_size_acres", type=float)
        prop.purchase_price = request.form.get("purchase_price", type=float)

        pd_raw = (request.form.get("purchase_date") or "").strip()
        if pd_raw:
            try:
                prop.purchase_date = datetime.strptime(pd_raw, "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            prop.purchase_date = None

        prop.notes = request.form.get("notes")

        # optional new profile photo
        file = request.files.get("profile_photo")
        if file and allowed_file(file.filename):
            filename = save_uploaded_photo(file, "property_profiles", prop.name or "property")
            prop.profile_photo = filename

        db.session.commit()
        flash(f'Property "{prop.name}" updated', "success")
        return redirect(url_for("realestate.property_detail", id=prop.id))

    return render_template("realestate/property_form.html", property=prop, active="realestate")


@realestate_bp.route("/<int:id>/delete", methods=["POST"])
def delete_property(id):
    """Delete a property and all related maintenance, photos, vendors, and outbuildings."""
    prop = Property.query.get_or_404(id)

    # Delete maintenance (and files)
    maint_items = PropertyMaintenance.query.filter_by(property_id=prop.id).all()
    for m in maint_items:
        photos = PropertyMaintenancePhoto.query.filter_by(maintenance_id=m.id).all()
        for ph in photos:
            try:
                full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "maintenance_photos", ph.filename)
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception:
                pass
            db.session.delete(ph)
        db.session.delete(m)

    # Delete vendors
    vendors = PropertyVendor.query.filter_by(property_id=prop.id).all()
    for v in vendors:
        db.session.delete(v)

    # Delete outbuildings and their profile photos
    outbuildings = PropertyOutbuilding.query.filter_by(property_id=prop.id).all()
    for ob in outbuildings:
        try:
            if ob.profile_photo:
                p = os.path.join(current_app.config["UPLOAD_FOLDER"], "outbuilding_profiles", ob.profile_photo)
                if os.path.exists(p):
                    os.remove(p)
        except Exception:
            pass
        db.session.delete(ob)

    # Delete property profile photo
    try:
        if prop.profile_photo:
            p_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "property_profiles", prop.profile_photo)
            if os.path.exists(p_path):
                os.remove(p_path)
    except Exception:
        pass

    db.session.delete(prop)
    db.session.commit()
    flash("Property deleted", "success")
    return redirect(url_for("realestate.dashboard"))


# ---------------- Vendors (Add / Edit / Delete) ----------------

@realestate_bp.route("/<int:property_id>/vendors/add", methods=["GET", "POST"])
def add_vendor(property_id):
    prop = Property.query.get_or_404(property_id)

    if request.method == "POST":
        vendor = PropertyVendor(
            property_id=property_id,
            company_name=(request.form.get("company_name") or "").strip(),
            service_type=(request.form.get("service_type") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            notes=request.form.get("notes"),
        )
        if not vendor.company_name:
            flash("Company name is required.", "error")
            return render_template("realestate/vendor_form.html", property=prop, vendor=None, active="realestate")

        db.session.add(vendor)
        db.session.commit()
        flash("Vendor added", "success")
        return redirect(url_for("realestate.property_detail", id=property_id))

    return render_template("realestate/vendor_form.html", property=prop, vendor=None, active="realestate")


@realestate_bp.route("/<int:property_id>/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
def edit_vendor(property_id, vendor_id):
    prop = Property.query.get_or_404(property_id)
    vendor = PropertyVendor.query.get_or_404(vendor_id)
    if vendor.property_id != property_id:
        flash("Vendor does not belong to this property.", "error")
        return redirect(url_for("realestate.property_detail", id=property_id))

    if request.method == "POST":
        vendor.company_name = (request.form.get("company_name") or "").strip()
        vendor.service_type = (request.form.get("service_type") or "").strip()
        vendor.phone = (request.form.get("phone") or "").strip()
        vendor.email = (request.form.get("email") or "").strip()
        vendor.notes = request.form.get("notes")

        if not vendor.company_name:
            flash("Company name is required.", "error")
            return render_template("realestate/vendor_form.html", property=prop, vendor=vendor, active="realestate")

        db.session.commit()
        flash("Vendor updated", "success")
        return redirect(url_for("realestate.property_detail", id=property_id))

    return render_template("realestate/vendor_form.html", property=prop, vendor=vendor, active="realestate")


@realestate_bp.route("/<int:property_id>/vendors/<int:vendor_id>/delete", methods=["POST"])
def delete_vendor(property_id, vendor_id):
    vendor = PropertyVendor.query.get_or_404(vendor_id)
    if vendor.property_id != property_id:
        flash("Vendor does not belong to this property.", "error")
        return redirect(url_for("realestate.property_detail", id=property_id))

    db.session.delete(vendor)
    db.session.commit()
    flash("Vendor deleted", "success")
    return redirect(url_for("realestate.property_detail", id=property_id))


# ---------------- Maintenance (Add / Edit / Delete) ----------------

@realestate_bp.route("/<int:property_id>/maintenance/add", methods=["GET", "POST"])
def add_maintenance(property_id):
    prop = Property.query.get_or_404(property_id)

    if request.method == "POST":
        category = (request.form.get("category") or "Other").strip()
        task = (request.form.get("task") or "").strip()

        date_str = (request.form.get("date_completed") or "").strip()
        try:
            date_completed = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else datetime.utcnow().date()
        except ValueError:
            date_completed = datetime.utcnow().date()

        maint = PropertyMaintenance(
            property_id=property_id,
            category=category,
            task=task,
            description=request.form.get("description"),
            date_completed=date_completed,
            performed_by=request.form.get("performed_by"),
            cost=request.form.get("cost", type=float) or 0.0,
        )

        db.session.add(maint)
        db.session.flush()  # for maint.id

        # Work photos (multiple)
        files = request.files.getlist("photos")
        for f in files:
            if f and allowed_file(f.filename):
                filename = save_uploaded_photo(f, "maintenance_photos", task or "maintenance")
                db.session.add(PropertyMaintenancePhoto(
                    maintenance_id=maint.id,
                    filename=filename,
                    photo_type="general",
                ))

        # Receipt (single)
        receipt = request.files.get("receipt")
        if receipt and allowed_file(receipt.filename):
            rname = save_uploaded_photo(receipt, "maintenance_photos", (task or "maintenance") + "_receipt")
            db.session.add(PropertyMaintenancePhoto(
                maintenance_id=maint.id,
                filename=rname,
                photo_type="receipt",
            ))

        db.session.commit()
        flash("Maintenance record added", "success")
        return redirect(url_for("realestate.property_detail", id=property_id))

    return render_template("realestate/maintenance_form.html", property=prop, active="realestate")


@realestate_bp.route("/<int:property_id>/maintenance/<int:maint_id>/edit", methods=["GET", "POST"])
def edit_maintenance(property_id, maint_id):
    prop = Property.query.get_or_404(property_id)
    maint = PropertyMaintenance.query.get_or_404(maint_id)
    if maint.property_id != property_id:
        flash("Maintenance item does not belong to this property.", "error")
        return redirect(url_for("realestate.property_detail", id=property_id))

    if request.method == "POST":
        maint.category = (request.form.get("category") or "Other").strip()
        maint.task = (request.form.get("task") or "").strip()
        maint.description = request.form.get("description")
        maint.performed_by = request.form.get("performed_by")
        maint.cost = request.form.get("cost", type=float) or 0.0

        date_str = (request.form.get("date_completed") or "").strip()
        try:
            maint.date_completed = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else maint.date_completed
        except ValueError:
            pass

        # Add more work photos
        files = request.files.getlist("photos")
        for f in files:
            if f and allowed_file(f.filename):
                filename = save_uploaded_photo(f, "maintenance_photos", maint.task or "maintenance")
                db.session.add(PropertyMaintenancePhoto(
                    maintenance_id=maint.id,
                    filename=filename,
                    photo_type="general",
                ))

        # Optional new receipt
        receipt = request.files.get("receipt")
        if receipt and allowed_file(receipt.filename):
            rname = save_uploaded_photo(receipt, "maintenance_photos", (maint.task or "maintenance") + "_receipt")
            db.session.add(PropertyMaintenancePhoto(
                maintenance_id=maint.id,
                filename=rname,
                photo_type="receipt",
            ))

        db.session.commit()
        flash("Maintenance updated", "success")
        return redirect(url_for("realestate.property_detail", id=property_id))

    photos = (
        PropertyMaintenancePhoto.query
        .filter_by(maintenance_id=maint.id)
        .order_by(PropertyMaintenancePhoto.uploaded_at.desc())
        .all()
    )
    return render_template(
        "realestate/maintenance_edit.html",
        property=prop,
        maint=maint,
        photos=photos,
        active="realestate",
    )


@realestate_bp.route("/<int:property_id>/maintenance/<int:maint_id>/delete", methods=["POST"])
def delete_maintenance(property_id, maint_id):
    maint = PropertyMaintenance.query.get_or_404(maint_id)
    if maint.property_id != property_id:
        flash("Item does not belong to this property.", "error")
        return redirect(url_for("realestate.property_detail", id=property_id))

    photos = PropertyMaintenancePhoto.query.filter_by(maintenance_id=maint.id).all()
    for ph in photos:
        try:
            full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "maintenance_photos", ph.filename)
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception:
            pass
        db.session.delete(ph)

    db.session.delete(maint)
    db.session.commit()
    flash("Maintenance deleted", "success")
    return redirect(url_for("realestate.property_detail", id=property_id))


@realestate_bp.route("/<int:property_id>/maintenance/<int:maint_id>/photo/<int:photo_id>/delete", methods=["POST"])
def delete_maintenance_photo(property_id, maint_id, photo_id):
    maint = PropertyMaintenance.query.get_or_404(maint_id)
    photo = PropertyMaintenancePhoto.query.get_or_404(photo_id)
    if maint.property_id != property_id or photo.maintenance_id != maint_id:
        flash("Photo does not match this maintenance item.", "error")
        return redirect(url_for("realestate.property_detail", id=property_id))

    try:
        full_path = os.path.join(current_app.config()["UPLOAD_FOLDER"], "maintenance_photos", photo.filename)
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception:
        pass

    db.session.delete(photo)
    db.session.commit()
    flash("Photo removed", "success")
    return redirect(url_for("realestate.edit_maintenance", property_id=property_id, maint_id=maint_id))


# ---------------- Outbuildings (Add / Edit / Delete) ----------------

@realestate_bp.route("/<int:property_id>/outbuildings/add", methods=["GET", "POST"])
def add_outbuilding(property_id):
    prop = Property.query.get_or_404(property_id)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "error")
            return render_template("realestate/outbuilding_form.html", property=prop, outbuilding=None, active="realestate")

        ob = PropertyOutbuilding(
            property_id=property_id,
            name=name,
            type=(request.form.get("type") or "").strip(),
            year_built=request.form.get("year_built", type=int),
            square_footage=request.form.get("square_footage", type=int),
            notes=request.form.get("notes"),
        )

        # Optional profile photo
        f = request.files.get("profile_photo")
        if f and allowed_file(f.filename):
            os.makedirs(os.path.join(current_app.config['UPLOAD_FOLDER'], 'outbuilding_profiles'), exist_ok=True)
            fname = save_uploaded_photo(f, "outbuilding_profiles", name or "outbuilding")
            ob.profile_photo = fname

        db.session.add(ob)
        db.session.commit()
        flash("Outbuilding added", "success")
        return redirect(url_for("realestate.property_detail", id=property_id))

    return render_template("realestate/outbuilding_form.html", property=prop, outbuilding=None, active="realestate")


@realestate_bp.route("/<int:property_id>/outbuildings/<int:ob_id>/edit", methods=["GET", "POST"])
def edit_outbuilding(property_id, ob_id):
    prop = Property.query.get_or_404(property_id)
    ob = PropertyOutbuilding.query.get_or_404(ob_id)
    if ob.property_id != property_id:
        flash("Outbuilding does not belong to this property.", "error")
        return redirect(url_for("realestate.property_detail", id=property_id))

    if request.method == "POST":
        ob.name = (request.form.get("name") or "").strip()
        ob.type = (request.form.get("type") or "").strip()
        ob.year_built = request.form.get("year_built", type=int)
        ob.square_footage = request.form.get("square_footage", type=int)
        ob.notes = request.form.get("notes")

        f = request.files.get("profile_photo")
        if f and allowed_file(f.filename):
            os.makedirs(os.path.join(current_app.config['UPLOAD_FOLDER'], 'outbuilding_profiles'), exist_ok=True)
            fname = save_uploaded_photo(f, "outbuilding_profiles", ob.name or "outbuilding")
            ob.profile_photo = fname

        db.session.commit()
        flash("Outbuilding updated", "success")
        return redirect(url_for("realestate.property_detail", id=property_id))

    return render_template("realestate/outbuilding_form.html", property=prop, outbuilding=ob, active="realestate")


@realestate_bp.route("/<int:property_id>/outbuildings/<int:ob_id>/delete", methods=["POST"])
def delete_outbuilding(property_id, ob_id):
    ob = PropertyOutbuilding.query.get_or_404(ob_id)
    if ob.property_id != property_id:
        flash("Outbuilding does not belong to this property.", "error")
        return redirect(url_for("realestate.property_detail", id=property_id))

    try:
        if ob.profile_photo:
            p = os.path.join(current_app.config['UPLOAD_FOLDER'], 'outbuilding_profiles', ob.profile_photo)
            if os.path.exists(p):
                os.remove(p)
    except Exception:
        pass

    db.session.delete(ob)
    db.session.commit()
    flash("Outbuilding deleted", "success")
    return redirect(url_for("realestate.property_detail", id=property_id))

@realestate_bp.route("/<int:property_id>/costs")
def cost_analysis(property_id):
    """Simple cost analysis dashboard"""
    prop = Property.query.get_or_404(property_id)
    
    # Get all maintenance records
    maintenance = PropertyMaintenance.query.filter_by(property_id=property_id).all()
    
    # Current year calculations
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Calculate category totals (all-time)
    category_costs = {}
    category_costs_yearly = {}  # Just this year
    
    for record in maintenance:
        category = record.category or 'Other'
        cost = record.cost or 0
        
        # All-time totals
        if category not in category_costs:
            category_costs[category] = 0
        category_costs[category] += cost
        
        # This year only
        if record.date_completed and record.date_completed.year == current_year:
            if category not in category_costs_yearly:
                category_costs_yearly[category] = 0
            category_costs_yearly[category] += cost
    
    # Calculate monthly spending for current year
    monthly_costs = [0] * 12
    for record in maintenance:
        if record.date_completed and record.date_completed.year == current_year:
            month_idx = record.date_completed.month - 1
            monthly_costs[month_idx] += record.cost or 0
    
    # Year totals
    yearly_total = sum(category_costs_yearly.values())
    
    # Last year comparison
    last_year_total = 0
    for record in maintenance:
        if record.date_completed and record.date_completed.year == (current_year - 1):
            last_year_total += record.cost or 0
    
    # Calculate YTD (Year to Date) - only completed months
    ytd_total = sum(monthly_costs[:current_month])
    
    # Average per month (only for completed months)
    monthly_avg = ytd_total / current_month if current_month > 0 else 0
    
    # Cost per square foot
    cost_per_sqft = yearly_total / (prop.square_footage or 1) if prop.square_footage else 0
    
    # Sort categories by cost for better chart display
    sorted_categories = dict(sorted(category_costs_yearly.items(), key=lambda x: x[1], reverse=True))
    
    # Get top spending category
    top_category = max(sorted_categories, key=sorted_categories.get) if sorted_categories else None
    top_category_amount = sorted_categories[top_category] if top_category else 0
    
    return render_template(
        "realestate/cost_analysis.html",
        property=prop,
        category_costs=sorted_categories,
        yearly_total=yearly_total,
        last_year_total=last_year_total,
        monthly_costs=monthly_costs,
        monthly_avg=monthly_avg,
        cost_per_sqft=cost_per_sqft,
        ytd_total=ytd_total,
        current_year=current_year,
        top_category=top_category,
        top_category_amount=top_category_amount,
        active="realestate"
    )


@realestate_bp.route("/<int:property_id>/costs/insights")
def cost_insights(property_id):
    """Generate AI-style insights from the maintenance data"""
    prop = Property.query.get_or_404(property_id)
    maintenance = PropertyMaintenance.query.filter_by(property_id=property_id).all()
    
    insights = []
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Calculate this year vs last year
    this_year_total = sum(r.cost or 0 for r in maintenance 
                         if r.date_completed and r.date_completed.year == current_year)
    last_year_total = sum(r.cost or 0 for r in maintenance 
                         if r.date_completed and r.date_completed.year == current_year - 1)
    
    if last_year_total > 0:
        change_pct = ((this_year_total - last_year_total) / last_year_total) * 100
        if change_pct > 20:
            insights.append(f"📈 Maintenance costs are up {change_pct:.0f}% from last year")
        elif change_pct < -20:
            insights.append(f"📉 Great job! Costs are down {abs(change_pct):.0f}% from last year")
        else:
            insights.append(f"📊 Costs are relatively stable (only {abs(change_pct):.0f}% change from last year)")
    
    # Seasonal analysis
    if len(maintenance) > 10:  # Need enough data
        summer_costs = sum(r.cost or 0 for r in maintenance 
                          if r.date_completed and r.date_completed.month in [6,7,8] 
                          and r.date_completed.year == current_year)
        winter_costs = sum(r.cost or 0 for r in maintenance 
                          if r.date_completed and r.date_completed.month in [12,1,2] 
                          and r.date_completed.year >= current_year - 1)
        
        if summer_costs > winter_costs * 1.5 and summer_costs > 100:
            insights.append("☀️ You spend significantly more in summer months (likely lawn care)")
        elif winter_costs > summer_costs * 1.5 and winter_costs > 100:
            insights.append("❄️ Winter is your expensive season (heating/snow removal?)")
    
    # Category insights
    category_costs = {}
    for record in maintenance:
        if record.date_completed and record.date_completed.year == current_year:
            cat = record.category or 'Other'
            category_costs[cat] = category_costs.get(cat, 0) + (record.cost or 0)
    
    if category_costs:
        top_category = max(category_costs, key=category_costs.get)
        top_pct = (category_costs[top_category] / this_year_total * 100) if this_year_total > 0 else 0
        
        if top_pct > 40:
            insights.append(f"🔧 {top_category} dominates at {top_pct:.0f}% of spending - might be worth getting quotes")
        
        # Check for neglected areas
        common_categories = ['HVAC', 'Plumbing', 'Lawn & Yard', 'Roof & Gutters']
        missing = [cat for cat in common_categories if cat not in category_costs]
        if missing and len(missing) <= 2:
            insights.append(f"🤔 No {missing[0]} maintenance this year - everything okay there?")
    
    # DIY vs Professional
    diy_count = sum(1 for r in maintenance 
                   if r.performed_by and 'self' in r.performed_by.lower() 
                   and r.date_completed and r.date_completed.year == current_year)
    pro_count = sum(1 for r in maintenance 
                   if r.performed_by and 'self' not in r.performed_by.lower() 
                   and r.date_completed and r.date_completed.year == current_year)
    
    if diy_count > pro_count * 2:
        insights.append("💪 You're a DIY champion! Doing most work yourself")
    elif pro_count > diy_count * 2:
        insights.append("👷 You prefer hiring pros - smart for complex jobs")
    
    # Cost prediction
    if current_month >= 6:  # Halfway through year
        projected_total = (this_year_total / current_month) * 12
        insights.append(f"📅 Based on current spending, projecting ${projected_total:,.0f} for the full year")
    
    # If no insights generated, add a default
    if not insights:
        insights.append("📊 Keep logging maintenance to unlock spending insights!")
    
    return jsonify({'insights': insights[:5]})  # Return top 5 insights

# Add this route to modules/realestate/routes.py
# This creates a master total page for all properties

@realestate_bp.route("/portfolio/costs")
def portfolio_costs():
    """Portfolio-wide cost analysis - all properties combined"""
    properties = Property.query.all()
    
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Master totals
    portfolio_stats = {
        'total_properties': len(properties),
        'properties_with_maintenance': 0,
        'total_spent_all_time': 0,
        'total_spent_this_year': 0,
        'total_spent_last_year': 0,
        'monthly_avg': 0,
        'most_expensive_property': None,
        'most_expensive_amount': 0
    }
    
    # Category totals across all properties
    master_category_costs = {}
    
    # Per-property breakdown
    property_costs = []
    
    # Monthly spending for chart (current year)
    monthly_portfolio_costs = [0] * 12
    
    for prop in properties:
        maintenance = PropertyMaintenance.query.filter_by(property_id=prop.id).all()
        
        if maintenance:
            portfolio_stats['properties_with_maintenance'] += 1
        
        # Calculate per-property totals
        property_total_all_time = 0
        property_total_this_year = 0
        property_total_last_year = 0
        property_categories = {}
        
        for record in maintenance:
            cost = record.cost or 0
            category = record.category or 'Other'
            
            # All-time total
            property_total_all_time += cost
            portfolio_stats['total_spent_all_time'] += cost
            
            # Category aggregation
            if category not in master_category_costs:
                master_category_costs[category] = 0
            master_category_costs[category] += cost
            
            if category not in property_categories:
                property_categories[category] = 0
            property_categories[category] += cost
            
            # Year-specific totals
            if record.date_completed:
                if record.date_completed.year == current_year:
                    property_total_this_year += cost
                    portfolio_stats['total_spent_this_year'] += cost
                    
                    # Monthly breakdown
                    month_idx = record.date_completed.month - 1
                    monthly_portfolio_costs[month_idx] += cost
                    
                elif record.date_completed.year == (current_year - 1):
                    property_total_last_year += cost
                    portfolio_stats['total_spent_last_year'] += cost
        
        # Track most expensive property
        if property_total_this_year > portfolio_stats['most_expensive_amount']:
            portfolio_stats['most_expensive_property'] = prop.name
            portfolio_stats['most_expensive_amount'] = property_total_this_year
        
        # Add to property list
        property_costs.append({
            'property': prop,
            'total_all_time': property_total_all_time,
            'total_this_year': property_total_this_year,
            'total_last_year': property_total_last_year,
            'top_category': max(property_categories, key=property_categories.get) if property_categories else None,
            'maintenance_count': len(maintenance)
        })
    
    # Sort properties by this year's spending
    property_costs.sort(key=lambda x: x['total_this_year'], reverse=True)
    
    # Calculate monthly average (YTD)
    portfolio_stats['monthly_avg'] = portfolio_stats['total_spent_this_year'] / current_month if current_month > 0 else 0
    
    # Sort categories by cost
    sorted_categories = dict(sorted(master_category_costs.items(), key=lambda x: x[1], reverse=True))
    
    # Calculate year-over-year change
    if portfolio_stats['total_spent_last_year'] > 0:
        yoy_change = ((portfolio_stats['total_spent_this_year'] - portfolio_stats['total_spent_last_year']) 
                     / portfolio_stats['total_spent_last_year']) * 100
    else:
        yoy_change = 0
    
    return render_template(
        "realestate/portfolio_costs.html",
        portfolio_stats=portfolio_stats,
        property_costs=property_costs,
        category_costs=sorted_categories,
        monthly_costs=monthly_portfolio_costs,
        current_year=current_year,
        yoy_change=yoy_change,
        active="realestate"
    )
