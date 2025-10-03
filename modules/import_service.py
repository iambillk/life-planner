# modules/rolodex/import_service.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
import csv, io, re

try:
    import vobject  # pip install vobject
except Exception:
    vobject = None

from models.base import db
from models.rolodex import Contact, Company  # your schema

# ---------- helpers ----------
_phone_rx = re.compile(r"\D+")
def norm_phone(p: Optional[str]) -> Optional[str]:
    if not p: return None
    s = p.strip()
    digits = _phone_rx.sub("", s)
    if s.startswith("+") and not digits.startswith("+"):
        return "+" + digits
    return digits or None

def lower_strip(s: Optional[str]) -> Optional[str]:
    return s.strip().lower() if s else None

def parse_date(s: Optional[str]) -> Optional[date]:
    if not s: return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

def get_or_create_company(name: Optional[str]) -> Optional[Company]:
    name = (name or "").strip()
    if not name: return None
    co = Company.query.filter(Company.name.ilike(name)).first()
    if not co:
        co = Company(name=name)
        db.session.add(co)
        db.session.flush()
    return co

@dataclass
class ImportRow:
    src_index: int
    # mapped fields for Contact
    first_name: str = ""
    last_name: str = ""
    display_name: str = ""
    title: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    personal_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    work_phone: Optional[str] = None
    home_phone: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    github_url: Optional[str] = None
    birthday: Optional[date] = None
    notes: str = ""
    company_name: Optional[str] = None  # used to look up/create Company

    # dedupe
    match_id: Optional[int] = None
    match_type: str = "new"  # "new" | "update" | "archived_match"
    errors: List[str] = field(default_factory=list)

def _compose_display(fn: str, ln: str, disp: str) -> str:
    disp = (disp or "").strip()
    if disp: return disp
    n = f"{(fn or '').strip()} {(ln or '').strip()}".strip()
    return n or "Unknown"

# ---------- CSV parsing ----------
def parse_csv(file_bytes: bytes) -> Tuple[List[ImportRow], List[str]]:
    text = file_bytes.decode(errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[ImportRow] = []
    errs: List[str] = []

    for i, r in enumerate(reader, 1):
        def g(*names):  # get first matching column
            for n in names:
                if n in r and r[n]: return r[n]
            return None

        first = g("first_name","first","given","given name","firstname")
        last  = g("last_name","last","family","family name","surname","lastname")
        disp  = g("display_name","name","full name","fullname") or ""
        email = g("email","email address","e-mail")
        email2= g("personal_email","alt email","alternate email")
        phone = g("phone","primary phone","main phone")
        mob   = g("mobile","mobile_phone","cell")
        work  = g("work_phone","work phone","office")
        home  = g("home_phone","home phone")
        title = g("title","job title")
        comp  = g("company","organization","org","employer")
        notes = g("notes","note")
        web   = g("website","url")
        bday  = g("birthday","birth date","dob")

        row = ImportRow(
            src_index=i,
            first_name=(first or "").strip(),
            last_name=(last or "").strip(),
            display_name=_compose_display(first or "", last or "", disp or ""),
            title=(title or "").strip(),
            email=lower_strip(email),
            personal_email=lower_strip(email2),
            phone=norm_phone(phone),
            mobile_phone=norm_phone(mob),
            work_phone=norm_phone(work),
            home_phone=norm_phone(home),
            website=(web or "").strip() or None,
            notes=(notes or "").strip(),
            company_name=(comp or "").strip() or None,
            birthday=parse_date(bday),
        )
        rows.append(row)
    return rows, errs

# ---------- VCF parsing ----------
def parse_vcf(file_bytes: bytes) -> Tuple[List[ImportRow], List[str]]:
    if vobject is None:
        return [], ["VCF parsing requires the 'vobject' package. Install it first."]
    text = file_bytes.decode(errors="ignore")
    blocks = re.split(r"(?=BEGIN:VCARD)", text, flags=re.IGNORECASE)
    rows: List[ImportRow] = []
    errs: List[str] = []
    idx = 0
    for block in blocks:
        if not block.strip(): continue
        idx += 1
        try:
            v = vobject.readOne(block)
        except Exception as e:
            errs.append(f"VCF parse error at block {idx}: {e}")
            continue

        fn = ""
        ln = ""
        disp = ""
        if getattr(v, "n", None) and v.n.value:
            n = v.n.value
            fn = (n.given or "").strip()
            ln = (n.family or "").strip()
        if getattr(v, "fn", None) and v.fn.value:
            disp = (v.fn.value or "").strip()

        title = ""
        comp = None
        if getattr(v, "title", None):
            title = (v.title.value or "").strip()
        if getattr(v, "org", None):
            orgv = v.org.value
            if isinstance(orgv, list) and orgv:
                comp = (orgv[0] or "").strip()
            elif isinstance(orgv, str):
                comp = orgv.strip()

        emails = []
        for e in getattr(v, "email_list", []):
            val = lower_strip(str(e.value or ""))
            if val and val not in emails: emails.append(val)

        tels = []
        for t in getattr(v, "tel_list", []):
            val = norm_phone(str(t.value or ""))
            if val and val not in tels: tels.append(val)

        notes = ""
        if getattr(v, "note", None):
            notes = (v.note.value or "").strip()

        bday = None
        if getattr(v, "bday", None):
            bday = parse_date(str(v.bday.value))

        url = None
        if getattr(v, "url", None):
            url = (v.url.value or "").strip()

        linkedin = twitter = facebook = instagram = github = None
        # Some exporters dump social URLs as additional URL fields; skip for brevity.

        row = ImportRow(
            src_index=idx,
            first_name=fn, last_name=ln,
            display_name=_compose_display(fn, ln, disp),
            title=title,
            email=emails[0] if emails else None,
            personal_email=emails[1] if len(emails) > 1 else None,
            phone=tels[0] if tels else None,
            mobile_phone=None,
            work_phone=None,
            home_phone=None,
            website=url,
            linkedin_url=linkedin,
            twitter_url=twitter,
            facebook_url=facebook,
            instagram_url=instagram,
            github_url=github,
            birthday=bday,
            notes=notes,
            company_name=comp,
        )
        rows.append(row)
    return rows, errs

# ---------- Dedupe ----------
def dedupe(rows: List[ImportRow]) -> List[ImportRow]:
    for r in rows:
        match = None
        if r.email:
            match = Contact.query.filter(Contact.email == r.email).first()
        if not match and r.phone:
            match = Contact.query.filter(Contact.phone == r.phone).first()

        if match:
            r.match_id = match.id
            r.match_type = "archived_match" if match.archived else "update"
        else:
            r.match_type = "new"
    return rows

# ---------- Persist ----------
def persist(rows: List[ImportRow]) -> Dict[str, int]:
    stats = {"created": 0, "updated": 0}
    for r in rows:
        # find or create
        c = None
        if r.match_id:
            c = Contact.query.get(r.match_id)
        elif r.email:
            c = Contact.query.filter(Contact.email == r.email).first()
        elif r.phone:
            c = Contact.query.filter(Contact.phone == r.phone).first()

        created = False
        if not c:
            c = Contact(display_name=r.display_name or "Unknown")
            db.session.add(c)
            created = True

        # update fields if present (do not blank out)
        def set_if(k, v):
            if v is not None and v != "":
                setattr(c, k, v)

        set_if("first_name", r.first_name)
        set_if("last_name", r.last_name)
        set_if("display_name", r.display_name)
        set_if("title", r.title)
        set_if("email", r.email)
        set_if("personal_email", r.personal_email)
        set_if("phone", r.phone)
        set_if("mobile_phone", r.mobile_phone)
        set_if("work_phone", r.work_phone)
        set_if("home_phone", r.home_phone)
        set_if("website", r.website)
        set_if("linkedin_url", r.linkedin_url)
        set_if("twitter_url", r.twitter_url)
        set_if("facebook_url", r.facebook_url)
        set_if("instagram_url", r.instagram_url)
        set_if("github_url", r.github_url)
        if r.birthday:
            c.birthday = r.birthday
        if r.notes:
            c.notes = (c.notes + ("\n\n" if c.notes else "") + r.notes).strip()

        # company
        if r.company_name:
            co = get_or_create_company(r.company_name)
            if co:
                c.company_id = co.id

        if c.archived:
            c.archived = False

        stats["created" if created else "updated"] += 1

    db.session.commit()
    return stats
