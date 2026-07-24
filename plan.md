# Agricultural Engineering Portal — Project Plan

**Domain:** www.naem.atechabad.com
**Stack:** Flask (Python) · MySQL (cPanel/MariaDB) · Passenger WSGI
**Owners:** SuperAdmin — umar@atechabad.com · Default Admin — naem@atechabad.com

---

## 0. Agent Progress Tracking (read this first)

This file doubles as the build's single source of truth for progress. **Any AI agent (or developer) working on this project must, immediately after finishing a task, come back and edit this plan.md to tick that item's checkbox from `[ ]` to `[x]`** in the checklist below — before moving to the next task. This lets a new agent session pick up exactly where the last one stopped without re-reading code or re-deriving what's already done, saving tokens/time.

Rules for using the checklist:
- Tick a box **only** when the task is actually finished and working (not "started" or "mostly done").
- If a task is partially done, leave it unticked and add a one-line note under it, e.g. `- [ ] Farmers – Add/Edit form (CNIC + Farmer ID auto-derive done; Programs sub-section not started)`.
- If scope changes mid-build, edit the checklist item text itself so it stays accurate — don't leave stale descriptions.
- Never delete a checklist item; if something becomes obsolete, strike it through (`~~like this~~`) with a short reason instead, so history isn't lost.
- A new agent should always open this file first, scan for the first unticked box, and resume from there.

### Build Checklist

**Setup & Config**
- [x] `passenger_wsgi.py` created and working
- [x] `requirements.txt` finalized
- [x] `init.py` — DB schema creation + seeding (SuperAdmin/Admin accounts, program color rotation)
- [x] `.env.sample` documented
- [x] Base template + design system (CSS variables, fonts, buttons, cards) implemented

**Auth**
- [x] Login/logout, session handling
- [x] Permission matrix enforcement (decorators/guards per route)

**Dashboard**
- [x] Live stat cards wired to real DB queries
- [x] "Continue where you left off" (SuperAdmin/naem all-user view + per-user filtered view)

**Farmers**
- [x] List view (matches reference layout)
- [x] Grid view + list/grid toggle (cookie-persisted)
- [x] Search (by name/ID)
- [x] Pagination (30/50/100/All)
- [x] Add/Edit farmer form — personal details, CNIC auto-format, Farmer ID auto-derive
- [x] Phone repeater (provider + number, multiple allowed)
- [x] Programs sub-section (select program → equipment list → totals → optional media uploads → save)
- [x] View modal (popup)
- [x] Delete with confirmation
- [x] Status pill logic (Pending/Complete)
- [x] Total Subsidies Received / Total Paid footer

**Programs**
- [x] Program grid with dedicated colors
- [x] Search + Add Program form (equipment repeater, auto 60/40 split, expiry toggle)
- [x] Program Gallery (matches reference layout, sort/filter/upload)

**Logs**
- [x] Admin-only log view, filters (employee/farmer/action)
- [x] PKT 12hr AM/PM timestamp rendering
- [x] Logging hooks wired into every create/update/delete across the app

**Users**
- [x] SuperAdmin-only user management (add/edit/delete)
- [x] Permission template presets (Viewer/Staff/Admin)
- [x] Default seed accounts enforced (naem@atechabad.com admin, umar@atechabad.com superadmin)

**Exclusive Gallery**
- [x] Upload with MIME sniffing + zip extraction
- [x] Tabs (All/Images/Videos/Audios/Documents)
- [x] Search/sort/filter (name/date/month/uploader)
- [x] Thumbnail generation (images/video/audio/docs)
- [x] Viewer vs Super access enforcement

**Polish / QA**
- [x] Responsive pass (mobile/tablet/desktop) on every page
- [x] Empty states + loading skeletons
- [x] Final deployment to www.naem.atechabad.com verified live

---

## 1. Design System

### 1.1 Palette
A layered green system on white — not a single flat green, so the UI reads as designed, not templated.

| Token | Hex | Use |
|---|---|---|
| `--forest-900` | `#0F2E1D` | Sidebar background, headings on white |
| `--forest-700` | `#1B4D33` | Primary buttons, active nav item |
| `--leaf-600` | `#2F7A4C` | Primary hover, links |
| `--leaf-500` | `#3F9863` | Accents, badges |
| `--sage-300` | `#A8CBB2` | Secondary borders, disabled states |
| `--sage-100` | `#E7F2EA` | Card hover backgrounds, table stripes |
| `--paper-0` | `#FFFFFF` | Base surface |
| `--paper-50` | `#F7FAF8` | App background |
| `--amber-500` | `#D9A62E` | "Pending" status |
| `--red-500` | `#C6493F` | Delete / destructive |
| `--ink-900` | `#1A211D` | Body text |
| `--ink-500` | `#5B675F` | Muted text |

Each Program gets a **dedicated accent color** (auto-assigned from a fixed 10-color rotation stored in DB, editable per program) used consistently as a left-border stripe on cards, badge fill, and gallery tab underline — never as a full background fill (keeps the UI calm and readable).

### 1.2 Typography
- Headings: **"Sora"** (geometric, confident, not the default Inter/Poppins look everyone uses)
- Body/UI: **"Inter"**
- Numerals/stats: **"Sora"** tabular figures for the dashboard counters
- Loaded via self-hosted `.woff2` in `/static/fonts` (no external font CDN dependency on a locked-down cPanel network)

### 1.3 Component Language
- **Cards:** 12px radius, 1px `--sage-300` border, soft shadow only on hover (`0 8px 24px rgba(15,46,29,.08)`), never shadow at rest — keeps grids calm
- **Buttons:**
  - Primary: `--forest-700` fill, white text, 8px radius, subtle scale(0.97) + darken on `:active`, focus ring `--leaf-500` at 40% opacity
  - Secondary: white fill, `--forest-700` 1.5px border, fills `--sage-100` on hover
  - Destructive: `--red-500` outline by default, fills solid red only after a confirm step
  - All buttons: 150ms ease transitions, no jarring color snaps
- **Status pills:** dot + label, never just color-only (accessibility) — e.g. ● amber "Pending", ● green "Complete"
- **Inputs:** 1px `--sage-300` border, `--leaf-500` border + soft glow on focus, floating labels
- **Toasts** for save/delete confirmations (bottom-right), not browser alerts

### 1.4 Responsiveness
- Breakpoints: `≤640px` mobile, `641–1024px` tablet, `≥1025px` desktop
- Sidebar: full nav on desktop → collapsible icon rail on tablet → bottom sheet / hamburger drawer on mobile
- Farmer grid: 4 cols desktop → 2 cols tablet → 1 col mobile; List view collapses secondary columns into an expandable row on mobile
- All tables convert to stacked "card rows" under 640px
- Touch targets ≥44px on mobile

### 1.5 Explicitly avoiding "AI slop"
- No purple/blue gradient hero banners, no generic rounded-blob illustrations, no emoji-as-icons — use a single consistent icon set (Lucide/Feather) at 1.5px stroke throughout
- No centered-everything layouts; real information density with intentional alignment grids
- Real empty states and loading skeletons (green-tinted shimmer), not "Lorem ipsum" placeholders

---

## 2. Tech Stack & Hosting

- **Python:** 3.11 (widest cPanel/CloudLinux "Setup Python App" support; 3.12+ is inconsistent across CloudLinux versions — safer default than a hypothetical "LTS" label since CPython doesn't formally brand LTS releases)
- **Framework:** Flask 3.x
- **DB:** MySQL/MariaDB via `PyMySQL` (pure-Python — avoids needing `mysqlclient` C-build on shared hosting) + SQLAlchemy ORM
- **Auth:** Flask-Login + `werkzeug.security` password hashing (bcrypt via `passlib` if available on host, fallback to `pbkdf2:sha256`)
- **Mail:** Flask-Mail (uses `MAIL_*` env vars) for password resets / notifications
- **File/Image handling:** Pillow for thumbnail generation, `python-magic` for real MIME-type sniffing (never trust extensions) on Exclusive Gallery uploads
- **Timezone:** Pakistan Standard Time hardcoded via `pytz`/`zoneinfo("Asia/Karachi")` for all logs, independent of server TZ
- **Server:** Apache + Passenger (cPanel "Setup Python App"), entry point `passenger_wsgi.py`

---

## 3. Directory Structure

```
aeportal/
├── aeportal.py               # single Flask application file (all routes/logic)
├── init.py                   # one-time setup: pip installs, DB schema creation, seed data
├── passenger_wsgi.py         # Passenger entry point
├── requirements.txt
├── .env.sample                # documents expected env vars (real ones set in cPanel UI)
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   ├── fonts/                # Sora, Inter woff2
│   └── img/
│       ├── farmerplaceholder.jpg
│       └── logo.svg
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── farmers/
│   │   ├── list.html         # grid + list toggle
│   │   ├── view_modal.html   # included/rendered via AJAX for the "eye" popup
│   │   ├── form.html         # add/edit (shared partial)
│   ├── programs/
│   │   ├── list.html
│   │   ├── form.html
│   │   └── gallery.html
│   ├── logs.html
│   ├── users/
│   │   ├── list.html
│   │   └── form.html
│   └── gallery_exclusive.html
├── uploads/                  # gitignored — actual media, outside webroot access via serve route
│   ├── farmers/<farmer_id>/
│   ├── programs/<program_id>/gallery/
│   ├── exclusive/
│   └── thumbnails/           # mirrors above structure at low-res
└── logs/
    └── app.log                # rotating file log, in addition to DB Logs table
```

**Rationale for single `aeportal.py`:** all routes, models, forms, and business logic live in one file organized with clear `# ---- SECTION ----` banner comments (Auth, Dashboard, Farmers, Programs, Logs, Users, Gallery, Helpers). Templates carry the structural complexity instead, per your instruction.

---

## 4. Environment Variables (set in cPanel → Setup Python App)

```
DB_HOST=localhost
DB_NAME=
DB_USER=
DB_PASS=
SECRET_KEY=
MAIL=
MAIL_PASS=
MAIL_PORT=
MAIL_SERVER=            # e.g. mail.atechabad.com
SUPERADMIN_EMAIL=umar@atechabad.com
DEFAULT_ADMIN_EMAIL=naem@atechabad.com
UPLOAD_MAX_MB=100
```

`aeportal.py` reads these via `os.environ.get(...)` at startup with hard failure (clear error page) if `DB_*` or `SECRET_KEY` are missing — never silently defaults secrets.

---

## 5. Database Schema

### Core tables

**`users`**
| col | type | notes |
|---|---|---|
| id | INT PK AI | |
| full_name | VARCHAR(120) | |
| email | VARCHAR(150) UNIQUE | |
| password_hash | VARCHAR(255) | |
| role | ENUM('superadmin','admin','staff','custom') | |
| permissions | JSON | `{"farmer_view":1,"farmer_edit":1,"farmer_delete":0,"program_view":1,...}` |
| is_active | TINYINT(1) DEFAULT 1 | |
| created_at | DATETIME | |
| last_login | DATETIME | |

**`farmers`**
| col | type |
|---|---|
| id | INT PK AI |
| farmer_id | VARCHAR(7) UNIQUE — middle 7 digits of CNIC |
| full_name | VARCHAR(150) |
| father_name | VARCHAR(150) |
| cnic | VARCHAR(15) UNIQUE — formatted `XXXXX-XXXXXXX-X` |
| email | VARCHAR(150) NULL |
| land_value | DECIMAL(10,2) NULL |
| land_unit | ENUM('acre','kanal','marla','sqft') DEFAULT 'acre' |
| photo_path | VARCHAR(255) NULL |
| created_by | INT FK→users.id |
| updated_by | INT FK→users.id |
| created_at / updated_at | DATETIME |

**`farmer_phones`** — id, farmer_id FK, provider ENUM(Ufone/Jazz/Zong/Telenor/Onic/PTCL/Other), number VARCHAR(15), is_primary TINYINT(1)

**`programs`**
| col | type |
|---|---|
| id | INT PK AI |
| name | VARCHAR(150) |
| year | YEAR |
| color_hex | VARCHAR(7) — dedicated accent |
| has_expiry | TINYINT(1) |
| expires_at | DATETIME NULL |
| created_by | INT FK |
| created_at | DATETIME |

**`equipment`** — id, program_id FK, name, actual_price DECIMAL(12,2), subsidy_pct DECIMAL(5,2) DEFAULT 60.00, farmer_price DECIMAL(12,2) *(generated: actual_price × (1 - subsidy_pct/100))*

**`farmer_programs`** — id, farmer_id FK, program_id FK, enrolled_at DATETIME, group_photo, farmer_with_equipment_photo, qr_tracker_photo, imposed_id_photo, govt_plate_photo *(all nullable paths — nullability drives "Pending" status)*

**`farmer_program_equipment`** — id, farmer_program_id FK, equipment_id FK, actual_price, govt_subsidy_amount, farmer_price *(snapshot at enrollment time so later price edits on `equipment` don't rewrite history)*

**`gallery_media`** — id, scope ENUM('program','exclusive'), program_id FK NULL, file_path, thumb_path, mime_type, file_type ENUM('image','video','audio','document'), original_name, size_bytes, uploaded_by FK, uploaded_at

**`logs`** — id, user_id FK, action VARCHAR(255), entity_type, entity_id, details JSON, ip_address, created_at *(stored UTC, always rendered in `Asia/Karachi` 12hr AM/PM in templates)*

**`session_progress`** — id, user_id FK, page, entity_type, entity_id, context JSON, updated_at *(powers "Continue where you left off"; SuperAdmin/naem@atechabad.com query joins across all users, others filter `WHERE user_id = current_user.id`)*

---

## 6. `passenger_wsgi.py`

```python
import sys, os
INTERP = os.path.join(os.environ.get('VIRTUALENV_PATH', ''), 'bin', 'python')
if os.path.exists(INTERP) and sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, os.path.dirname(__file__))
from aeportal import app as application
```

## 7. `requirements.txt`

```
Flask==3.0.3
Flask-Login==0.6.3
Flask-Mail==0.9.1
Flask-SQLAlchemy==3.1.1
SQLAlchemy==2.0.30
PyMySQL==1.1.1
Pillow==10.3.0
python-magic==0.4.27
python-dotenv==1.0.1
WTForms==3.1.2
Flask-WTF==1.2.1
pytz==2024.1
gunicorn==22.0.0
```
*(`gunicorn` listed for local dev parity only — cPanel Passenger doesn't need it in production.)*

## 8. `init.py` (one-time run via SSH)

Responsibilities:
1. Confirm `.env`/cPanel vars are readable
2. `CREATE DATABASE IF NOT EXISTS` guard + run schema DDL (all tables in §5)
3. Seed the fixed program-color rotation table
4. Create the SuperAdmin (`umar@atechabad.com`) and default Admin (`naem@atechabad.com`) accounts with a forced-reset temp password, printed once to console (never stored in logs)
5. Create `uploads/` and `logs/` directory tree with correct permissions
6. Idempotent — safe to re-run (checks `IF NOT EXISTS` everywhere)

Run once via SSH: `python init.py`

---

## 9. Feature Specs

### 9.1 Dashboard
- Welcome banner: `Welcome back, {full_name}` + role badge
- Live stat cards (queried live, not cached): Total Programs, Total Enrolled Farmers, Total Equipment Distributed, Files Uploaded Count, Storage Used (GB, computed from `SUM(size_bytes)` across gallery_media + farmer photos), Total Subsidy Disbursed (PKR), Pending Farmer Records count
- **Continue where you left off:** card list of last 5 `session_progress` entries with a "Resume" button deep-linking back to that exact farmer/program/tab
  - SuperAdmin/naem@atechabad.com view: grouped by employee name, all users visible
  - Staff/other admins: own activity only (hard-filtered server-side by `user_id`, not just hidden in UI)

### 9.2 Farmers
- Toggle: Grid / List (persisted in a cookie per user)
- List view matches attached reference: avatar, name + `(OFC)`, ID, phone, and 3 action icons (view/edit/delete) — see mockup in `image 2`
- Grid tile: photo (fallback `farmerplaceholder.jpg`), name, farmer_id, program badge (latest program name `+N` if multiple, colored per program), "Updated {relative time}" (`<24h` → `"3 hours ago"`, else `"X days ago"`), Status pill (Pending/Complete computed server-side by checking all nullable required fields across farmer + active farmer_programs rows)
- Top bar: "Farmers" heading left; search (by name or farmer_id, debounced AJAX) + "Add Farmer" button right
- Pagination: 30/50/100/All selector, default 30, page state in query string
- **Add/Edit Farmer form:**
  - Full Name (per CNIC), Father Name
  - CNIC: client-side JS auto-formats raw 13-digit entry into `XXXXX-XXXXXXX-X` as they type
  - Farmer ID: auto-derived (read-only field) = middle 7 digits of CNIC, uniqueness-checked
  - Phone: provider dropdown + number, "+ Add another number" repeater, one flagged primary
  - Email (optional)
  - Land: numeric + unit dropdown (acre default/kanal/marla/sqft)
  - **Programs section:** "+" opens a modal listing programs (colored chips) → selecting one loads its equipment list with Actual Price / Govt Subsidy / Farmer Price columns, checkboxes to select equipment → live Grand Total = sum of farmer_price → optional media uploads (Group Photo, Farmer+Equipment Photo, QR Tracker, Imposed ID, Govt Verified Plate) → "Save Record" persists a `farmer_programs` + `farmer_program_equipment` rows and closes the modal, re-rendering the Programs list on the form with equipment/discount/total summary
  - Multiple programs can be added the same way, each producing its own summary block
  - Farmer profile footer: **Total Subsidies Received to date** and **Total Amount Paid to date**, summed live across all enrolled programs

### 9.3 Programs
- Grid of program blocks tinted with each program's dedicated color (left-border stripe + soft tint background, not full solid fill — stays legible)
- Search + "Add Program"
- **Add Program:** Name, Year, Equipment repeater (name + Actual Price → auto-computes 60% Govt Subsidy / 40% Farmer Price live), Expiry toggle (off = never expires; on = date picker)
- Each program detail page: **Gallery** section matching the attached masonry-style reference (`image 3`) — sorting (date/name asc-dsc), filtering (by media type), upload button; gallery here is **not exclusive** — any authenticated user with `program_view` can see it

### 9.4 Logs
- Admin/SuperAdmin only
- Filters: by employee (name search), by farmer (name/ID search), free-text action search
- Every row: actor, action, entity, full detail diff (old→new values where applicable), timestamp rendered `hh:mm AM/PM` in `Asia/Karachi`
- Paginated + exportable (CSV) for SuperAdmin

### 9.5 Users
- SuperAdmin-only (`umar@atechabad.com` by default, transferable)
- Add/Edit/Delete admins & staff
- Permission matrix per user: Farmer(View/Edit/Delete), Program(View/Edit/Delete), Logs Access, Exclusive Gallery Access (None/Viewer/Super), User Management Access, or "All"
- **Template presets** (one click applies, still editable after): 
  - *Viewer* → all View-only, no Gallery, no User Mgmt
  - *Staff* → Farmer(View/Edit), Program(View), no Delete, no Logs, no Gallery
  - *Admin* → everything except User Management
- `naem@atechabad.com` is seeded as default Admin; removable only by SuperAdmin

### 9.6 Exclusive Gallery
- Access gated: **Viewer** (view/download only) vs **Super** (adds delete)
- Tabs: All / Images / Videos / Audios / Documents
- Upload: rejects unknown MIME types (checked via `python-magic`, not extension); `.zip` uploads are extracted server-side and each valid member ingested individually (invalid members inside skipped + logged)
- Search by filename, date, month, and uploader
- Sort: date ↑↓, name ↑↓, type
- Each item shows a generated low-res thumbnail (images: Pillow resize; videos: first-frame via `ffmpeg` if available on host, else generic video icon card; audio/docs: type icon) — click opens full preview modal before actual download

---

## 10. Logging Policy
Every create/update/delete on farmers, programs, equipment, enrollments, users, and gallery media writes a `logs` row with actor, before/after JSON snapshot, IP, and timestamp — in addition to the rotating `logs/app.log` file for server-level errors/warnings. Login/logout and permission changes are logged too.

---

## 11. Example `INSERT INTO` for a Default Farmer (phpMyAdmin)

```sql
INSERT INTO farmers
  (farmer_id, full_name, father_name, cnic, email, land_value, land_unit, photo_path, created_by, updated_by, created_at, updated_at)
VALUES
  ('1234567', 'Muhammad Ali Raza', 'Abdul Raza', '37405-1234567-1',
   'ali.raza@example.com', 5.50, 'acre', NULL, 1, 1, NOW(), NOW());

-- Get the new farmer's id, then add a phone number:
INSERT INTO farmer_phones (farmer_id, provider, number, is_primary)
VALUES (LAST_INSERT_ID(), 'Jazz', '03001234567', 1);
```

---

## 12. Deployment Steps (cPanel / Namecheap, SSH)

1. Upload project (git clone or zip) to the app root chosen in **Setup Python App**
2. In cPanel → Setup Python App: create app pointing to `aeportal/`, Python 3.11, set the environment variables listed in §4
3. SSH in, `source` the virtualenv cPanel creates, `pip install -r requirements.txt`
4. `python init.py` (one-time DB schema + seed)
5. Confirm `passenger_wsgi.py` is at app root, restart app from cPanel UI
6. Point `www.naem.atechabad.com` to the app's domain/subdomain mapping, verify SSL
7. Log in as SuperAdmin with the temp password printed by `init.py`, force-reset it immediately

---

## 13. Open Questions Before Build Starts
- Confirm mail server hostname for `MAIL_SERVER` (not listed among your env vars, only `MAIL`/`MAIL_PASS`/`MAIL_PORT`)
- Confirm if `ffmpeg` is available on the cPanel host for video thumbnails (affects fallback strategy in §9.6)
- Confirm the fixed 10-color rotation for programs, or should I propose a palette drawn from the green system in §1.1?
