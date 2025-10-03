# modules/rolodex/routes_import.py
from flask import request, render_template, redirect, url_for, flash, session
from . import rolodex_bp  # your existing blueprint
from models.base import db
from modules.rolodex.import_service import parse_vcf, parse_csv, dedupe, persist, ImportRow

MAX_PREVIEW = 500  # safety cap

@rolodex_bp.route("/import", methods=["GET", "POST"])
def rolodex_import():
    if request.method == "GET":
        return render_template("rolodex/import_upload.html", active="rolodex")

    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a .vcf or .csv file.", "error")
        return redirect(url_for("rolodex.rolodex_import"))

    name = file.filename.lower()
    data = file.read()
    rows = []
    errors = []
    if name.endswith(".vcf") or name.endswith(".vcard"):
        rows, errors = parse_vcf(data)
    elif name.endswith(".csv"):
        rows, errors = parse_csv(data)
    else:
        # try VCF then CSV
        try:
            rows, errors = parse_vcf(data)
        except Exception:
            rows, errors = parse_csv(data)

    rows = dedupe(rows)

    # store preview in session (lightweight)
    preview = []
    for r in rows[:MAX_PREVIEW]:
        preview.append(r.__dict__)
    session["rolodex_import_preview"] = preview

    totals = {
        "total": len(rows),
        "previewed": len(preview),
        "new": sum(1 for r in rows if r.match_type == "new"),
        "update": sum(1 for r in rows if r.match_type == "update"),
        "archived_match": sum(1 for r in rows if r.match_type == "archived_match"),
        "errors": len(errors),
    }

    return render_template(
        "rolodex/import_preview.html",
        rows=rows[:MAX_PREVIEW],
        totals=totals,
        errors=errors,
        active="rolodex"
    )

@rolodex_bp.route("/import/commit", methods=["POST"])
def rolodex_import_commit():
    preview = session.get("rolodex_import_preview")
    if not preview:
        flash("Nothing to import. Start with an upload.", "error")
        return redirect(url_for("rolodex.rolodex_import"))

    # apply user selections; if none posted, assume all
    selected = request.form.getlist("row")
    selected_idx = set(int(x) for x in selected) if selected else None

    rows: list[ImportRow] = []
    for raw in preview:
        ir = ImportRow(**{k: raw[k] for k in raw.keys() if k != "errors"})
        if (selected_idx is None) or (ir.src_index in selected_idx):
            rows.append(ir)

    stats = persist(rows)
    session.pop("rolodex_import_preview", None)
    flash(f"Imported: {stats['created']} created, {stats['updated']} updated.", "success")
    return redirect(url_for("rolodex.contacts"))
