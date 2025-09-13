# ==================== EMAIL CAPTURE (PERSONAL) ====================

from urllib.parse import unquote_plus

def _clean_msgid(raw: str | None) -> str | None:
    if not raw:
        return None
    # raw may come like "<abc@ex>", sometimes URL-encoded
    try:
        raw = unquote_plus(raw)
    except Exception:
        pass
    raw = raw.strip()
    # strip angle brackets if present
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1]
    return raw.strip().lower()

def _clean_subject(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        s = unquote_plus(raw).strip()
    except Exception:
        s = raw.strip()
    # light cleanup for nicer titles
    for prefix in ("Re: ", "RE: ", "Fwd: ", "FWD: ", "[EXT] "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip()

@persprojects_bp.route('/capture/email/personal', methods=['GET'])
def capture_personal_get():
    """
    Confirm form for capturing a Personal Project from an email.
    Expects query params: msgid, from, subject (best-effort).
    Example hotkey URL (from The Bat! filter):
      /capture/email/personal?msgid=%OMSGID&from=%FROMADDR&subject=%SUBJECT
    """
    msgid_raw = request.args.get('msgid', '')
    from_addr = request.args.get('from', '')
    subject_raw = request.args.get('subject', '')

    msgid = _clean_msgid(msgid_raw)
    title_suggest = _clean_subject(subject_raw)

    # Pull ALL projects for the "Add to Existing" dropdown (per your preference)
    all_projects = PersonalProject.query.order_by(PersonalProject.created_at.desc()).all()

    # Optional soft dedupe check: look for any note that mentions this Message-ID
    dup = None
    if msgid:
        dup = (db.session.query(PersonalProjectNote, PersonalProject)
               .join(PersonalProject, PersonalProject.id == PersonalProjectNote.project_id)
               .filter(PersonalProjectNote.content.ilike(f"%Message-ID:%{msgid}%"))
               .first())

    return render_template(
        'persprojects/capture_personal.html',
        msgid=msgid,
        from_addr=from_addr,
        subject_raw=unquote_plus(subject_raw) if subject_raw else '',
        title_suggest=title_suggest,
        categories=PERSONAL_PROJECT_CATEGORIES,
        projects=all_projects,
        duplicate=dup  # None or (note, project)
    )

@persprojects_bp.route('/capture/email/personal', methods=['POST'])
def capture_personal_post():
    """
    Handle form submit from the capture page.
    Creates either a NEW PersonalProject or a TASK in an existing one.
    Stores a first note with From/Subject/Message-ID for traceability.
    """
    mode = request.form.get('mode', 'new')  # 'new' or 'existing'
    title = (request.form.get('title') or '').strip()
    category = request.form.get('category') or None
    due_date_str = request.form.get('due_date') or ''
    existing_id = request.form.get('existing_id') or ''
    from_addr = (request.form.get('from_addr') or '').strip()
    subject_raw = (request.form.get('subject_raw') or '').strip()
    msgid = _clean_msgid(request.form.get('msgid'))

    # Parse due date (optional)
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except Exception:
            due_date = None

    # Build a small structured note body for provenance
    provenance_lines = []
    if from_addr:
        provenance_lines.append(f"From: {from_addr}")
    if subject_raw:
        provenance_lines.append(f"Subject: {subject_raw}")
    if msgid:
        provenance_lines.append(f"Message-ID: {msgid}")
    provenance_lines.append(f"Captured: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')} via The Bat!")
    provenance = "\n".join(provenance_lines)

    # Soft dedupe: if user didn’t override and we already have a note with this msgid, nudge them
    if request.form.get('dedupe_override') != '1' and msgid:
        dup = (db.session.query(PersonalProjectNote, PersonalProject)
               .join(PersonalProject, PersonalProject.id == PersonalProjectNote.project_id)
               .filter(PersonalProjectNote.content.ilike(f"%Message-ID:%{msgid}%"))
               .first())
        if dup:
            note, project = dup
            flash('Looks like you already captured this email.', 'warning')
            # Re-render confirm with a banner + option to continue anyway
            all_projects = PersonalProject.query.order_by(PersonalProject.created_at.desc()).all()
            return render_template(
                'persprojects/capture_personal.html',
                msgid=msgid,
                from_addr=from_addr,
                subject_raw=subject_raw,
                title_suggest=title or _clean_subject(subject_raw),
                categories=PERSONAL_PROJECT_CATEGORIES,
                projects=all_projects,
                duplicate=dup,
                dedupe_can_override=True
            )

    if mode == 'existing' and existing_id:
        # Add a TASK to an existing project
        project = PersonalProject.query.get(int(existing_id))
        if not project:
            flash('Selected project not found.', 'error')
            return redirect(url_for('persprojects.index'))

        task = PersonalTask(
            project_id=project.id,
            content=title or _clean_subject(subject_raw),
            category=category or 'general',
        )
        db.session.add(task)
        db.session.flush()

        # Attach the provenance as task notes
        if provenance:
            task.notes = (task.notes or '').strip()
            task.notes = (task.notes + ("\n\n" if task.notes else "") + provenance).strip()

        db.session.commit()
        flash('Task created from email.', 'success')
        return redirect(url_for('persprojects.detail', id=project.id))

    # Default: create NEW Personal Project
    project = PersonalProject(
        name=title or _clean_subject(subject_raw) or 'New Personal Project',
        description='',  # can be edited later
        category=category or None,
        status='planning',
        priority='medium',
        deadline=due_date
    )
    db.session.add(project)
    db.session.flush()

    # First note with provenance (email context)
    note = PersonalProjectNote(
        project_id=project.id,
        content=provenance,
        category='reference'
    )
    db.session.add(note)
    db.session.commit()

    flash(f'Project "{project.name}" created from email.', 'success')
    return redirect(url_for('persprojects.detail', id=project.id))
