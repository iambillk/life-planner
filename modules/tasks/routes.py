# modules/tasks/routes.py
from datetime import datetime, date, timedelta
from flask import request, render_template, jsonify, flash
from . import tasks_bp

# Models (import softly so missing modules don’t break the page)
try:
    from models import db
except Exception:
    db = None

try:
    from models.persprojects import PersonalTask, PersonalProject
except Exception:
    PersonalTask = None
    PersonalProject = None

try:
    from models.projects import TCHTask, TCHProject
except Exception:
    TCHTask = None
    TCHProject = None

try:
    from models.standalone import StandaloneTask
except Exception:
    StandaloneTask = None


def _parse_filters():
    f = {
        'q': (request.args.get('q') or '').strip(),
        'source': (request.args.get('source') or 'all').lower(),      # all|personal|tch|standalone
        'priority': (request.args.get('priority') or 'all').lower(),  # all|low|medium|high|critical
        'status': (request.args.get('status') or 'open').lower(),     # open|completed|all
        'due': (request.args.get('due') or 'all').lower(),            # all|overdue|today|week
        'sort': (request.args.get('sort') or 'due_asc').lower(),      # due_asc|due_desc|prio|newest|oldest
        'page': max(1, int(request.args.get('page', 1))),
        'per_page': min(200, max(10, int(request.args.get('per_page', 50)))),
    }
    return f


def _collect_rows():
    """Return a list of normalized dict rows from all available sources."""
    rows = []

    # Personal
    if PersonalTask and PersonalProject:
        q = db.session.query(PersonalTask, PersonalProject).join(
            PersonalProject, PersonalProject.id == PersonalTask.project_id
        )
        for t, p in q.all():
            rows.append({
                'uid': f'pers-{t.id}',
                'source': 'personal',
                'raw_id': t.id,
                'project_id': t.project_id,
                'project_name': getattr(p, 'name', 'Personal'),
                'title': getattr(t, 'content', '') or '',
                'priority': (getattr(t, 'priority', None) or 'medium').lower(),
                'due_date': getattr(t, 'due_date', None),
                'completed': bool(getattr(t, 'completed', False)),
                'created_at': getattr(t, 'created_at', None) or datetime.utcnow(),
            })

    # TCH
    if TCHTask and TCHProject:
        q = db.session.query(TCHTask, TCHProject).join(
            TCHProject, TCHProject.id == TCHTask.project_id
        )
        for t, p in q.all():
            rows.append({
                'uid': f'tch-{t.id}',
                'source': 'tch',
                'raw_id': t.id,
                'project_id': t.project_id,
                'project_name': getattr(p, 'name', 'TCH'),
                'title': getattr(t, 'title', '') or '',
                'priority': (getattr(t, 'priority', None) or 'medium').lower(),
                'due_date': getattr(t, 'due_date', None),
                'completed': bool(getattr(t, 'completed', False)),
                'created_at': getattr(t, 'created_at', None) or datetime.utcnow(),
            })

    # Standalone
    if StandaloneTask:
        for t in db.session.query(StandaloneTask).all():
            rows.append({
                'uid': f'solo-{t.id}',
                'source': 'standalone',
                'raw_id': t.id,
                'project_id': None,
                'project_name': 'Inbox',
                'title': getattr(t, 'title', '') or '',
                'priority': (getattr(t, 'priority', None) or 'medium').lower(),
                'due_date': getattr(t, 'due_date', None),
                'completed': bool(getattr(t, 'completed', False)),
                'created_at': getattr(t, 'created_at', None) or datetime.utcnow(),
            })

    return rows


def _date_window(key: str):
    today = date.today()
    if key == 'overdue':
        # handled inline (due_date < today & not completed)
        return None, None
    if key == 'today':
        return today, today
    if key == 'week':
        return today, today + timedelta(days=7)
    return None, None


@tasks_bp.get('/tasks')
def index():
    f = _parse_filters()
    rows = _collect_rows()

    # Source filter
    if f['source'] in {'personal', 'tch', 'standalone'}:
        rows = [r for r in rows if r['source'] == f['source']]

    # Search (title/project_name)
    if f['q']:
        q = f['q'].lower()
        rows = [r for r in rows if q in (r['title'] or '').lower() or q in (r['project_name'] or '').lower()]

    # Priority
    if f['priority'] in {'low', 'medium', 'high', 'critical'}:
        rows = [r for r in rows if (r['priority'] or 'medium') == f['priority']]

    # Status
    if f['status'] in {'open', 'completed'}:
        want = (f['status'] == 'completed')
        rows = [r for r in rows if bool(r['completed']) == want]

    # Due
    today = date.today()
    if f['due'] == 'overdue':
        rows = [r for r in rows if (r['due_date'] is not None and r['due_date'] < today and not r['completed'])]
    elif f['due'] in {'today', 'week'}:
        start, end = _date_window(f['due'])
        if start and end:
            rows = [r for r in rows if (r['due_date'] is not None and start <= r['due_date'] <= end)]

    # Sort
    if f['sort'] == 'due_desc':
        rows.sort(key=lambda r: (r['due_date'] is None, r['due_date'] or date.min, r['created_at'] or datetime.min), reverse=True)
    elif f['sort'] == 'prio':
        weight = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
        rows.sort(key=lambda r: (weight.get(r['priority'] or 'medium', 1), r['due_date'] or date.max), reverse=True)
    elif f['sort'] == 'newest':
        rows.sort(key=lambda r: (r['created_at'] or datetime.min), reverse=True)
    elif f['sort'] == 'oldest':
        rows.sort(key=lambda r: (r['created_at'] or datetime.min))
    else:  # due_asc (default)
        rows.sort(key=lambda r: (r['due_date'] is None, r['due_date'] or date.max, -(r['created_at'] or datetime.min).timestamp()))

    # Pagination
    total = len(rows)
    start = (f['page'] - 1) * f['per_page']
    end = start + f['per_page']
    page_rows = rows[start:end]

    return render_template('tasks/index.html', rows=page_rows, f=f, total=total, today=today)


@tasks_bp.post('/tasks/toggle')
def toggle():
    uid = (request.form.get('uid') or '').strip()
    if not uid:
        return jsonify(ok=False, error='Missing uid'), 400

    try:
        prefix, raw = uid.split('-', 1)
        task_id = int(raw)
    except Exception:
        return jsonify(ok=False, error='Bad uid'), 400

    now = datetime.utcnow()

    if prefix == 'tch' and TCHTask and db:
        t = TCHTask.query.get_or_404(task_id)
        t.completed = not t.completed
        if hasattr(t, 'completed_date'):
            t.completed_date = now if t.completed else None
        elif hasattr(t, 'completed_at'):
            t.completed_at = now if t.completed else None
        db.session.commit()
        return jsonify(ok=True, completed=bool(t.completed))

    if prefix == 'pers' and PersonalTask and db:
        t = PersonalTask.query.get_or_404(task_id)
        t.completed = not t.completed
        if hasattr(t, 'completed_at'):
            t.completed_at = now if t.completed else None
        db.session.commit()
        return jsonify(ok=True, completed=bool(t.completed))

    if prefix == 'solo' and StandaloneTask and db:
        t = StandaloneTask.query.get_or_404(task_id)
        t.completed = not t.completed
        if hasattr(t, 'completed_at'):
            t.completed_at = now if t.completed else None
        db.session.commit()
        return jsonify(ok=True, completed=bool(t.completed))

    return jsonify(ok=False, error='Unknown source or model missing'), 400


@tasks_bp.post('/tasks/add')
def add_standalone():
    if not (StandaloneTask and db):
        return jsonify(ok=False, error='StandaloneTask not enabled (migrations not run)'), 400

    title = (request.form.get('title') or '').strip()
    priority = (request.form.get('priority') or 'medium').lower()
    notes = (request.form.get('notes') or '').strip()
    due_str = (request.form.get('due_date') or '').strip()

    if not title:
        return jsonify(ok=False, error='Title required'), 400

    due_date = None
    if due_str:
        try:
            due_date = datetime.strptime(due_str, '%Y-%m-%d').date()
        except Exception:
            due_date = None

    t = StandaloneTask(title=title, priority=priority, notes=notes, due_date=due_date)
    db.session.add(t)
    db.session.commit()
    return jsonify(ok=True, uid=f'solo-{t.id}')
