import os
import sys
import json
import zipfile
import mimetypes
from datetime import datetime, timezone
import pytz

basedir = os.path.abspath(os.path.dirname(__file__))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(basedir, '.env'))
except ImportError:
    pass

from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify,
    send_from_directory, Response, make_response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')

# Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-aeportal-secret-key-12345')

from urllib.parse import quote_plus

# DB Configuration (MySQL phpMyAdmin / PyMySQL for production, SQLite fallback for local development)
host = os.environ.get('DB_HOST', 'localhost')
user = os.environ.get('DB_USER', 'cpanel_username_dbuser')
password = os.environ.get('DB_PASS', 'db_password')
database = os.environ.get('DB_NAME', 'cpanel_username_dbname')

db_path = os.path.join(os.path.dirname(__file__), 'aeportal.db')
sqlite_uri = f"sqlite:///{db_path}"

# Try MySQL connection if configured and reachable; fallback to SQLite for local execution if MySQL is absent
try:
    import pymysql
    conn = pymysql.connect(host=host, user=user, password=password, database=database, connect_timeout=2)
    conn.close()
    encoded_pass = quote_plus(password) if password else ''
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{user}:{encoded_pass}@{host}/{database}?charset=utf8mb4"
except Exception:
    app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_uri

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('UPLOAD_MAX_MB', 100)) * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

PKT_TZ = pytz.timezone('Asia/Karachi')

# ---- JINJA FILTERS & CONTEXT PROCESSORS ----
@app.template_filter('pkt_time')
def pkt_time_filter(dt):
    if not dt:
        return ''
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    pkt_dt = dt.astimezone(PKT_TZ)
    return pkt_dt.strftime('%Y-%m-%d %I:%M %p')

@app.template_filter('relative_time')
def relative_time_filter(dt):
    if not dt:
        return ''
    now = datetime.utcnow()
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 3600:
        mins = int(seconds / 60)
        return f"{max(mins, 1)} min{'s' if mins != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

@app.context_processor
def inject_globals():
    return {'datetime': datetime}

# ---- MODELS ----
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='staff') # superadmin, admin, staff, custom
    permissions = db.Column(db.Text, nullable=False, default='{}') # JSON string
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_perms(self):
        try:
            return json.loads(self.permissions)
        except Exception:
            return {}

    def has_perm(self, perm_key):
        if self.role == 'superadmin':
            return True
        perms = self.get_perms()
        val = perms.get(perm_key, 0)
        return val != 0 and val != 'none'

class Farmer(db.Model):
    __tablename__ = 'farmers'
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.String(7), unique=True, nullable=False) # middle 7 digits of CNIC
    full_name = db.Column(db.String(150), nullable=False)
    father_name = db.Column(db.String(150), nullable=False)
    cnic = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(150), nullable=True)
    land_value = db.Column(db.Numeric(10, 2), nullable=True)
    land_unit = db.Column(db.String(20), default='acre')
    photo_path = db.Column(db.String(255), nullable=True)
    house_address = db.Column(db.String(255), nullable=True)
    city_tehsil = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    province = db.Column(db.String(100), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    phones = db.relationship('FarmerPhone', backref='farmer', cascade='all, delete-orphan')
    enrollments = db.relationship('FarmerProgram', backref='farmer', cascade='all, delete-orphan')

class LandDocument(db.Model):
    __tablename__ = 'land_documents'
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('farmers.id'), nullable=False)
    doc_type = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    farmer = db.relationship('Farmer', backref=db.backref('land_documents', cascade='all, delete-orphan'))

class FarmerPhone(db.Model):
    __tablename__ = 'farmer_phones'
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('farmers.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    number = db.Column(db.String(15), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)

class Program(db.Model):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    color_hex = db.Column(db.String(7), nullable=False, default='#2F7A4C')
    has_expiry = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    thumbnail_path = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    equipment = db.relationship('Equipment', backref='program', cascade='all, delete-orphan')
    enrollments = db.relationship('FarmerProgram', backref='program', cascade='all, delete-orphan')

class ProgramColorRotation(db.Model):
    __tablename__ = 'program_color_rotation'
    id = db.Column(db.Integer, primary_key=True)
    color_hex = db.Column(db.String(7), nullable=False)
    color_name = db.Column(db.String(50), nullable=False)
    is_used = db.Column(db.Boolean, default=False)

class Equipment(db.Model):
    __tablename__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    actual_price = db.Column(db.Numeric(12, 2), nullable=False)
    subsidy_pct = db.Column(db.Numeric(5, 2), default=60.00)
    farmer_price = db.Column(db.Numeric(12, 2), nullable=False)

class FarmerProgram(db.Model):
    __tablename__ = 'farmer_programs'
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('farmers.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_photo = db.Column(db.String(255), nullable=True)
    farmer_with_equipment_photo = db.Column(db.String(255), nullable=True)
    qr_tracker_photo = db.Column(db.String(255), nullable=True)
    imposed_id_photo = db.Column(db.String(255), nullable=True)
    govt_plate_photo = db.Column(db.String(255), nullable=True)
    cnic_front_photo = db.Column(db.String(255), nullable=True)
    cnic_back_photo = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Active')

    selected_equipment = db.relationship('FarmerProgramEquipment', backref='farmer_program', cascade='all, delete-orphan')

class FarmerProgramEquipment(db.Model):
    __tablename__ = 'farmer_program_equipment'
    id = db.Column(db.Integer, primary_key=True)
    farmer_program_id = db.Column(db.Integer, db.ForeignKey('farmer_programs.id'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    actual_price = db.Column(db.Numeric(12, 2), nullable=False)
    govt_subsidy_amount = db.Column(db.Numeric(12, 2), nullable=False)
    farmer_price = db.Column(db.Numeric(12, 2), nullable=False)

    equipment = db.relationship('Equipment')

class GalleryMedia(db.Model):
    __tablename__ = 'gallery_media'
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(20), nullable=False) # 'program', 'exclusive'
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=True)
    file_path = db.Column(db.String(255), nullable=False)
    thumb_path = db.Column(db.String(255), nullable=True)
    mime_type = db.Column(db.String(100), nullable=False)
    file_type = db.Column(db.String(20), nullable=False) # 'image', 'video', 'audio', 'document'
    original_name = db.Column(db.String(255), nullable=False)
    size_bytes = db.Column(db.BigInteger, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='logs')

class SessionProgress(db.Model):
    __tablename__ = 'session_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    page = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    context = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='session_progress')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---- AUTOMATIC DB & SEED USER CHECK ON STARTUP ----
def ensure_db_seeded():
    with app.app_context():
        db.create_all()
        # Seed SuperAdmin if missing
        umar = User.query.filter_by(email='umar@atechabad.com').first()
        if not umar:
            umar = User(
                full_name='Umar (SuperAdmin)',
                email='umar@atechabad.com',
                role='superadmin',
                permissions=json.dumps({"farmer_view":1,"farmer_edit":1,"farmer_delete":1,"program_view":1,"program_edit":1,"program_delete":1,"logs_access":1,"gallery_access":"super","user_mgmt":1}),
                is_active=True
            )
            umar.set_password('Admin@123456')
            db.session.add(umar)

        # Seed Default Admin if missing
        naem = User.query.filter_by(email='naem@atechabad.com').first()
        if not naem:
            naem = User(
                full_name='Naeem (Admin)',
                email='naem@atechabad.com',
                role='admin',
                permissions=json.dumps({"farmer_view":1,"farmer_edit":1,"farmer_delete":1,"program_view":1,"program_edit":1,"program_delete":1,"logs_access":1,"gallery_access":"super","user_mgmt":0}),
                is_active=True
            )
            naem.set_password('Admin@123456')
            db.session.add(naem)

        db.session.commit()

        # Database Auto-Migration Check for Farmers & FarmerProgram columns
        try:
            bind = db.engine
            from sqlalchemy import inspect
            inspector = inspect(bind)
            columns = [c['name'] for c in inspector.get_columns('farmers')]
            
            if 'house_address' not in columns:
                db.session.execute(db.text("ALTER TABLE farmers ADD COLUMN house_address VARCHAR(255) NULL"))
            if 'city_tehsil' not in columns:
                db.session.execute(db.text("ALTER TABLE farmers ADD COLUMN city_tehsil VARCHAR(100) NULL"))
            if 'district' not in columns:
                db.session.execute(db.text("ALTER TABLE farmers ADD COLUMN district VARCHAR(100) NULL"))
            if 'province' not in columns:
                db.session.execute(db.text("ALTER TABLE farmers ADD COLUMN province VARCHAR(100) NULL"))
            
            columns_fp = [c['name'] for c in inspector.get_columns('farmer_programs')]
            if 'status' not in columns_fp:
                db.session.execute(db.text("ALTER TABLE farmer_programs ADD COLUMN status VARCHAR(20) DEFAULT 'Active' NOT NULL"))
            if 'cnic_front_photo' not in columns_fp:
                db.session.execute(db.text("ALTER TABLE farmer_programs ADD COLUMN cnic_front_photo VARCHAR(255) NULL"))
            if 'cnic_back_photo' not in columns_fp:
                db.session.execute(db.text("ALTER TABLE farmer_programs ADD COLUMN cnic_back_photo VARCHAR(255) NULL"))
                
            db.session.commit()
        except Exception as e:
            print("DB Schema Migration check warning:", e)
            db.session.rollback()

# Ensure DB tables & default admin accounts exist automatically
ensure_db_seeded()

# ---- UTILS & MIME SNIFFER ----
def get_file_mime(filepath):
    try:
        import magic
        mime = magic.from_file(filepath, mime=True)
        if mime:
            return mime
    except Exception:
        pass
    mime, _ = mimetypes.guess_type(filepath)
    return mime or 'application/octet-stream'

def log_activity(action, entity_type=None, entity_id=None, details=None, user_id=None):
    if user_id is None and current_user and current_user.is_authenticated:
        user_id = current_user.id
    
    ip = request.remote_addr if request else '127.0.0.1'
    details_str = json.dumps(details) if isinstance(details, (dict, list)) else details

    log_entry = Log(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details_str,
        ip_address=ip,
        created_at=datetime.utcnow()
    )
    db.session.add(log_entry)
    
    # Write to log file
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, 'app.log'), 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.utcnow().isoformat()}] User:{user_id} IP:{ip} Action:{action} Entity:{entity_type}:{entity_id}\n")

def track_progress(page, entity_type=None, entity_id=None, context=None):
    if not current_user or not current_user.is_authenticated:
        return
    ctx_str = json.dumps(context) if isinstance(context, (dict, list)) else context
    sp = SessionProgress.query.filter_by(user_id=current_user.id, page=page, entity_id=entity_id).first()
    if sp:
        sp.context = ctx_str
        sp.updated_at = datetime.utcnow()
    else:
        sp = SessionProgress(
            user_id=current_user.id,
            page=page,
            entity_type=entity_type,
            entity_id=entity_id,
            context=ctx_str,
            updated_at=datetime.utcnow()
        )
        db.session.add(sp)
    db.session.commit()

def calculate_farmer_status(farmer):
    if not farmer.enrollments:
        return 'pending'
    for en in farmer.enrollments:
        if not (en.group_photo and en.farmer_with_equipment_photo and en.qr_tracker_photo and en.imposed_id_photo and en.govt_plate_photo):
            return 'pending'
    return 'complete'

def generate_thumbnail(source_path, dest_thumb_path):
    try:
        os.makedirs(os.path.dirname(dest_thumb_path), exist_ok=True)
        with Image.open(source_path) as img:
            img.thumbnail((300, 300))
            img.save(dest_thumb_path)
        return True
    except Exception:
        return False

# ---- AUTH ROUTES ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact administrator.', 'error')
                return render_template('login.html')
            
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            log_activity("User logged in", entity_type="user", entity_id=user.id)
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity("User logged out", entity_type="user", entity_id=current_user.id)
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# ---- DASHBOARD ROUTE ----
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    track_progress('dashboard')
    
    # Query Live Stats
    total_programs = Program.query.count()
    total_farmers = Farmer.query.count()
    total_equipment = FarmerProgramEquipment.query.count()
    total_files = GalleryMedia.query.count()
    
    # Authentic Real Storage Calculation (Scans actual uploads directory on disk)
    upload_dir = app.config.get('UPLOAD_FOLDER', os.path.join(basedir, 'uploads'))
    total_bytes = 0
    if os.path.exists(upload_dir):
        for root_dir, _, filenames in os.walk(upload_dir):
            for fn in filenames:
                try:
                    fp = os.path.join(root_dir, fn)
                    total_bytes += os.path.getsize(fp)
                except OSError:
                    pass
    
    gallery_bytes = db.session.query(db.func.sum(GalleryMedia.size_bytes)).scalar() or 0
    total_bytes = max(total_bytes, gallery_bytes)

    storage_used_mb = round(total_bytes / (1024 * 1024), 2)
    storage_used_gb = round(total_bytes / (1024 * 1024 * 1024), 3)

    storage_total_gb = float(os.environ.get('STORAGE_TOTAL_GB', 10.0))
    storage_total_bytes = storage_total_gb * 1024 * 1024 * 1024

    storage_percent = round((total_bytes / storage_total_bytes) * 100, 2) if storage_total_bytes > 0 else 0.0
    if storage_percent > 100.0:
        storage_percent = 100.0

    if storage_used_gb >= 0.1:
        storage_used_str = f"{round(storage_used_gb, 2)} GB"
    else:
        storage_used_str = f"{storage_used_mb} MB"
    
    storage_total_str = f"{int(storage_total_gb) if storage_total_gb.is_integer() else storage_total_gb} GB"
    
    # Total Subsidy Disbursed
    total_subsidy = db.session.query(db.func.sum(FarmerProgramEquipment.govt_subsidy_amount)).scalar() or 0.00
    
    # Pending Farmer Records
    farmers = Farmer.query.all()
    pending_count = sum(1 for f in farmers if calculate_farmer_status(f) == 'pending')
    
    # Continue Where You Left Off:
    if current_user.role == 'superadmin' or current_user.email == 'naem@atechabad.com':
        recent_sessions = SessionProgress.query.order_by(SessionProgress.updated_at.desc()).limit(8).all()
    else:
        recent_sessions = SessionProgress.query.filter_by(user_id=current_user.id).order_by(SessionProgress.updated_at.desc()).limit(5).all()

    return render_template('dashboard.html',
        total_programs=total_programs,
        total_farmers=total_farmers,
        total_equipment=total_equipment,
        total_files=total_files,
        storage_gb=storage_used_gb,
        storage_used=storage_used_str,
        storage_total=storage_total_str,
        storage_percent=storage_percent,
        total_subsidy=total_subsidy,
        pending_count=pending_count,
        recent_sessions=recent_sessions
    )

# ---- FARMERS ROUTES ----
@app.route('/farmers')
@login_required
def farmers_list():
    if not current_user.has_perm('farmer_view'):
        flash('Permission denied.', 'error')
        return redirect(url_for('dashboard'))
    
    track_progress('farmers_list')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page_str = request.args.get('per_page', '30')

    query = Farmer.query
    if search:
        query = query.filter(db.or_(Farmer.full_name.ilike(f"%{search}%"), Farmer.farmer_id.ilike(f"%{search}%"), Farmer.cnic.ilike(f"%{search}%")))

    if per_page_str == 'all':
        farmers_items = query.order_by(Farmer.updated_at.desc()).all()
        pagination = None
    else:
        per_page = int(per_page_str)
        pagination = query.order_by(Farmer.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        farmers_items = pagination.items

    farmer_data = []
    for f in farmers_items:
        primary_phone = FarmerPhone.query.filter_by(farmer_id=f.id, is_primary=True).first()
        if not primary_phone:
            primary_phone = FarmerPhone.query.filter_by(farmer_id=f.id).first()
        phone_str = primary_phone.number if primary_phone else 'N/A'
        
        status = calculate_farmer_status(f)
        latest_program = f.enrollments[-1].program if f.enrollments else None
        prog_count = len(f.enrollments)

        farmer_data.append({
            'farmer': f,
            'phone': phone_str,
            'status': status,
            'latest_program': latest_program.name if latest_program else None,
            'latest_program_color': latest_program.color_hex if latest_program else '#2F7A4C',
            'prog_count': prog_count
        })

    return render_template('farmers/list.html',
        farmers=farmer_data,
        pagination=pagination,
        search=search,
        per_page=per_page_str
    )

@app.route('/farmers/add', methods=['GET', 'POST'])
@app.route('/farmers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def farmer_form(id=None):
    if not current_user.has_perm('farmer_edit'):
        flash('Permission denied.', 'error')
        return redirect(url_for('farmers_list'))

    farmer = Farmer.query.get_or_404(id) if id else None
    programs = Program.query.order_by(Program.name).all()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        father_name = request.form.get('father_name', '').strip()
        cnic = request.form.get('cnic', '').strip()
        farmer_id = request.form.get('farmer_id', '').strip()
        email = request.form.get('email', '').strip() or None
        land_value = request.form.get('land_value', type=float) or None
        land_unit = request.form.get('land_unit', 'acre')

        # Check unique CNIC / Farmer ID
        existing_cnic = Farmer.query.filter(Farmer.cnic == cnic, Farmer.id != (farmer.id if farmer else 0)).first()
        if existing_cnic:
            flash(f"A farmer with CNIC {cnic} already exists.", "error")
            return render_template('farmers/form.html', farmer=farmer, programs=programs, total_subsidy_received=0, total_amount_paid=0)

        house_address = request.form.get('house_address', '').strip() or None
        city_tehsil = request.form.get('city_tehsil', '').strip() or None
        district = request.form.get('district', '').strip() or None
        province = request.form.get('province', '').strip() or None

        if not farmer:
            farmer = Farmer(
                farmer_id=farmer_id,
                full_name=full_name,
                father_name=father_name,
                cnic=cnic,
                email=email,
                land_value=land_value,
                land_unit=land_unit,
                house_address=house_address,
                city_tehsil=city_tehsil,
                district=district,
                province=province,
                created_by=current_user.id,
                updated_by=current_user.id
            )
            db.session.add(farmer)
            db.session.flush()
            log_action = "Created farmer profile"
        else:
            farmer.full_name = full_name
            farmer.father_name = father_name
            farmer.cnic = cnic
            farmer.farmer_id = farmer_id
            farmer.email = email
            farmer.land_value = land_value
            farmer.land_unit = land_unit
            farmer.house_address = house_address
            farmer.city_tehsil = city_tehsil
            farmer.district = district
            farmer.province = province
            farmer.updated_by = current_user.id
            log_action = "Updated farmer profile"

        if 'photo' in request.files and request.files['photo'].filename:
            file = request.files['photo']
            fname = secure_filename(f"farmer_{farmer.id}_{file.filename}")
            up_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'farmers', str(farmer.id))
            os.makedirs(up_dir, exist_ok=True)
            path = os.path.join(up_dir, fname)
            file.save(path)
            farmer.photo_path = f"farmers/{farmer.id}/{fname}"

        # Phone numbers
        FarmerPhone.query.filter_by(farmer_id=farmer.id).delete()
        providers = request.form.getlist('phone_provider[]')
        numbers = request.form.getlist('phone_number[]')
        primary_idx = request.form.get('primary_phone_index', 0, type=int)

        for idx, (prov, num) in enumerate(zip(providers, numbers)):
            if num.strip():
                is_pri = (idx == primary_idx)
                db.session.add(FarmerPhone(farmer_id=farmer.id, provider=prov, number=num.strip(), is_primary=is_pri))

        # Land Documents
        doc_types = request.form.getlist('doc_type[]')
        doc_files = request.files.getlist('doc_file[]')
        existing_docs = LandDocument.query.filter_by(farmer_id=farmer.id).all()
        new_docs = []
        
        for i, dtype in enumerate(doc_types):
            file_path = None
            if i < len(existing_docs):
                file_path = existing_docs[i].file_path
            
            if i < len(doc_files) and doc_files[i] and doc_files[i].filename:
                f = doc_files[i]
                fname = secure_filename(f"doc_{i}_{int(datetime.utcnow().timestamp())}_{f.filename}")
                up_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'farmers', str(farmer.id), 'documents')
                os.makedirs(up_dir, exist_ok=True)
                fpath = os.path.join(up_dir, fname)
                f.save(fpath)
                
                if file_path:
                    old_fpath = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
                    if os.path.exists(old_fpath):
                        try:
                            os.remove(old_fpath)
                        except OSError:
                            pass
                
                file_path = f"farmers/{farmer.id}/documents/{fname}"
                
            if file_path:
                new_docs.append(LandDocument(
                    farmer_id=farmer.id,
                    doc_type=dtype,
                    file_path=file_path
                ))
                
        LandDocument.query.filter_by(farmer_id=farmer.id).delete()
        for nd in new_docs:
            db.session.add(nd)

        # Inline Program Enrollment (When creating a new farmer or enrolling from form)
        enroll_program_id = request.form.get('enroll_program_id', type=int)
        if enroll_program_id:
            prog = Program.query.get(enroll_program_id)
            if prog:
                existing_en = FarmerProgram.query.filter_by(farmer_id=farmer.id, program_id=prog.id).first()
                if not existing_en:
                    enrollment = FarmerProgram(farmer_id=farmer.id, program_id=prog.id, enrolled_at=datetime.utcnow(), status='Active')
                    db.session.add(enrollment)
                    db.session.flush()

                    eq_ids = request.form.getlist('enroll_equipment_ids[]')
                    for eq_id in eq_ids:
                        eq = Equipment.query.filter_by(id=eq_id, program_id=prog.id).first()
                        if eq:
                            govt_sub = eq.actual_price * (eq.subsidy_pct / 100)
                            f_price = eq.actual_price - govt_sub
                            fpe = FarmerProgramEquipment(
                                farmer_program_id=enrollment.id,
                                equipment_id=eq.id,
                                actual_price=eq.actual_price,
                                govt_subsidy_amount=govt_sub,
                                farmer_price=f_price
                            )
                            db.session.add(fpe)

                    photo_fields = ['group_photo', 'farmer_with_equipment_photo', 'qr_tracker_photo', 'imposed_id_photo', 'govt_plate_photo', 'cnic_front_photo', 'cnic_back_photo']
                    up_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'farmers', str(farmer.id), f"prog_{prog.id}")
                    os.makedirs(up_dir, exist_ok=True)

                    for field in photo_fields:
                        if field in request.files and request.files[field].filename:
                            f = request.files[field]
                            fname = secure_filename(f"{field}_{enrollment.id}_{f.filename}")
                            fpath = os.path.join(up_dir, fname)
                            f.save(fpath)
                            setattr(enrollment, field, f"farmers/{farmer.id}/prog_{prog.id}/{fname}")

        db.session.commit()
        log_activity(log_action, entity_type="farmer", entity_id=farmer.id, details={"name": farmer.full_name, "cnic": farmer.cnic})
        track_progress('farmer_form', entity_type='farmer', entity_id=farmer.id)

        flash('Farmer profile saved successfully.', 'success')
        return redirect(url_for('farmers_list'))

    total_subsidy_received = 0.00
    total_amount_paid = 0.00
    if farmer:
        for en in farmer.enrollments:
            for eq in en.selected_equipment:
                total_subsidy_received += float(eq.govt_subsidy_amount)
                total_amount_paid += float(eq.farmer_price)

    return render_template('farmers/form.html',
        farmer=farmer,
        programs=programs,
        total_subsidy_received=total_subsidy_received,
        total_amount_paid=total_amount_paid
    )

@app.route('/farmers/<int:id>/enroll-program', methods=['POST'])
@login_required
def farmer_enroll_program(id):
    if not current_user.has_perm('farmer_edit'):
        return jsonify({'error': 'Permission denied'}), 403

    farmer = Farmer.query.get_or_404(id)
    program_id = request.form.get('program_id', type=int)
    program = Program.query.get_or_404(program_id)

    enrollment = FarmerProgram(farmer_id=farmer.id, program_id=program.id, enrolled_at=datetime.utcnow())
    db.session.add(enrollment)
    db.session.flush()

    photo_fields = ['group_photo', 'farmer_with_equipment_photo', 'qr_tracker_photo', 'imposed_id_photo', 'govt_plate_photo', 'cnic_front_photo', 'cnic_back_photo']
    up_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'farmers', str(farmer.id), f"prog_{program.id}")
    os.makedirs(up_dir, exist_ok=True)

    for field in photo_fields:
        if field in request.files and request.files[field].filename:
            f = request.files[field]
            fname = secure_filename(f"{field}_{enrollment.id}_{f.filename}")
            fpath = os.path.join(up_dir, fname)
            f.save(fpath)
            setattr(enrollment, field, f"farmers/{farmer.id}/prog_{program.id}/{fname}")

    eq_ids = request.form.getlist('equipment_ids[]')
    for eq_id in eq_ids:
        eq = Equipment.query.get(int(eq_id))
        if eq:
            govt_sub = eq.actual_price * (eq.subsidy_pct / 100)
            f_price = eq.actual_price - govt_sub
            fpe = FarmerProgramEquipment(
                farmer_program_id=enrollment.id,
                equipment_id=eq.id,
                actual_price=eq.actual_price,
                govt_subsidy_amount=govt_sub,
                farmer_price=f_price
            )
            db.session.add(fpe)

    db.session.commit()
    log_activity("Enrolled farmer in program", entity_type="farmer_program", entity_id=enrollment.id)
    flash(f"Enrolled in {program.name} successfully.", 'success')
    return redirect(url_for('farmer_form', id=farmer.id))

@app.route('/farmers/<int:id>/view-modal')
@login_required
def farmer_view_modal(id):
    farmer = Farmer.query.get_or_404(id)
    status = calculate_farmer_status(farmer)
    return render_template('farmers/view_modal.html', farmer=farmer, status=status)

@app.route('/farmer/<int:farmer_id>/view')
@app.route('/farmers/<int:farmer_id>/view')
@login_required
def farmer_view(farmer_id):
    if not current_user.has_perm('farmer_view'):
        flash('Permission denied.', 'error')
        return redirect(url_for('farmers_list'))
    
    farmer = Farmer.query.options(
        db.joinedload(Farmer.phones),
        db.joinedload(Farmer.land_documents),
        db.joinedload(Farmer.enrollments).joinedload(FarmerProgram.program),
        db.joinedload(Farmer.enrollments).joinedload(FarmerProgram.selected_equipment)
    ).get_or_404(farmer_id)
    
    status = calculate_farmer_status(farmer)
    
    total_subsidy_received = 0.00
    total_amount_paid = 0.00
    for en in farmer.enrollments:
        for eq in en.selected_equipment:
            total_subsidy_received += float(eq.govt_subsidy_amount or 0)
            total_amount_paid += float(eq.farmer_price or 0)
            
    # Safely get back url or redirect to farmer list
    back_url = request.referrer or url_for('farmers_list')
    
    return render_template('farmers/view.html',
        farmer=farmer,
        status=status,
        total_subsidy_received=total_subsidy_received,
        total_amount_paid=total_amount_paid,
        back_url=back_url
    )

@app.route('/farmers/<int:id>/delete', methods=['POST'])
@login_required
def farmer_delete(id):
    if not current_user.has_perm('farmer_delete'):
        flash('Permission denied.', 'error')
        return redirect(url_for('farmers_list'))

    farmer = Farmer.query.get_or_404(id)
    farmer_name = farmer.full_name
    db.session.delete(farmer)
    db.session.commit()
    log_activity("Deleted farmer record", entity_type="farmer", entity_id=id, details={"name": farmer_name})
    flash(f"Farmer '{farmer_name}' deleted.", 'success')
    return redirect(url_for('farmers_list'))

# ---- PROGRAMS ROUTES ----
@app.route('/programs')
@login_required
def programs_list():
    if not current_user.has_perm('program_view'):
        flash('Permission denied.', 'error')
        return redirect(url_for('dashboard'))

    track_progress('programs_list')
    search = request.args.get('search', '').strip()
    query = Program.query
    if search:
        query = query.filter(Program.name.ilike(f"%{search}%"))

    programs = query.options(
        db.joinedload(Program.enrollments),
        db.joinedload(Program.equipment)
    ).order_by(Program.created_at.desc()).all()
    return render_template('programs/list.html', programs=programs, search=search)

@app.route('/programs/<int:id>')
@app.route('/program/<int:id>')
@app.route('/programs/<int:id>/details')
@login_required
def program_detail(id):
    if not current_user.has_perm('program_view'):
        flash('Permission denied.', 'error')
        return redirect(url_for('dashboard'))

    program = Program.query.options(
        db.joinedload(Program.enrollments).joinedload(FarmerProgram.farmer),
        db.joinedload(Program.enrollments).joinedload(FarmerProgram.selected_equipment),
        db.joinedload(Program.equipment)
    ).get_or_404(id)

    track_progress('program_detail', entity_type='program', entity_id=program.id)

    total_farmers = len(program.enrollments)
    total_subsidy_disbursed = 0.0
    total_farmer_contribution = 0.0

    for en in program.enrollments:
        for eq in en.selected_equipment:
            total_subsidy_disbursed += float(eq.govt_subsidy_amount or 0)
            total_farmer_contribution += float(eq.farmer_price or 0)

    return render_template('programs/detail.html',
        program=program,
        total_farmers=total_farmers,
        total_subsidy_disbursed=total_subsidy_disbursed,
        total_farmer_contribution=total_farmer_contribution
    )

@app.route('/programs/add', methods=['GET', 'POST'])
@app.route('/programs/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def program_form(id=None):
    if not current_user.has_perm('program_edit'):
        flash('Permission denied.', 'error')
        return redirect(url_for('programs_list'))

    program = Program.query.options(
        db.joinedload(Program.enrollments).joinedload(FarmerProgram.farmer),
        db.joinedload(Program.enrollments).joinedload(FarmerProgram.selected_equipment)
    ).get_or_404(id) if id else None
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        year = request.form.get('year', type=int) or datetime.utcnow().year
        color_hex = request.form.get('color_hex', '#2F7A4C')
        has_expiry = 'has_expiry' in request.form
        expires_at_str = request.form.get('expires_at', '')
        expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d') if (has_expiry and expires_at_str) else None

        if not program:
            if not color_hex or color_hex == '#2F7A4C':
                avail_color = ProgramColorRotation.query.filter_by(is_used=False).first()
                if not avail_color:
                    ProgramColorRotation.query.update({ProgramColorRotation.is_used: False})
                    avail_color = ProgramColorRotation.query.first()
                color_hex = avail_color.color_hex if avail_color else '#2F7A4C'
                if avail_color:
                    avail_color.is_used = True

            program = Program(
                name=name,
                year=year,
                color_hex=color_hex,
                has_expiry=has_expiry,
                expires_at=expires_at,
                created_by=current_user.id
            )
            db.session.add(program)
            db.session.flush()
            log_act = "Created program scheme"
        else:
            program.name = name
            program.year = year
            program.color_hex = color_hex
            program.has_expiry = has_expiry
            program.expires_at = expires_at
            log_act = "Updated program scheme"

        eq_ids = request.form.getlist('equipment_id[]')
        eq_names = request.form.getlist('equipment_name[]')
        actual_prices = request.form.getlist('actual_price[]')
        subsidy_pcts = request.form.getlist('subsidy_pct[]')

        if not eq_ids:
            eq_ids = [''] * len(eq_names)

        kept_eq_ids = []
        for eq_id_str, eq_n, a_p, s_p in zip(eq_ids, eq_names, actual_prices, subsidy_pcts):
            if eq_n.strip() and a_p:
                act_p = float(a_p)
                sub_pct = float(s_p) if s_p else 60.00
                f_p = act_p * (1 - sub_pct / 100)
                
                eq_item = None
                if eq_id_str and str(eq_id_str).isdigit():
                    eq_item = Equipment.query.filter_by(id=int(eq_id_str), program_id=program.id).first()

                if eq_item:
                    eq_item.name = eq_n.strip()
                    eq_item.actual_price = act_p
                    eq_item.subsidy_pct = sub_pct
                    eq_item.farmer_price = f_p
                else:
                    eq_item = Equipment(
                        program_id=program.id,
                        name=eq_n.strip(),
                        actual_price=act_p,
                        subsidy_pct=sub_pct,
                        farmer_price=f_p
                    )
                    db.session.add(eq_item)
                    db.session.flush()
                kept_eq_ids.append(eq_item.id)

        old_eqs = Equipment.query.filter_by(program_id=program.id).all()
        for old_eq in old_eqs:
            if old_eq.id not in kept_eq_ids:
                is_referenced = FarmerProgramEquipment.query.filter_by(equipment_id=old_eq.id).first()
                if not is_referenced:
                    db.session.delete(old_eq)

        # Thumbnail upload handling
        remove_thumbnail = request.form.get('remove_thumbnail') in ('1', 'true', 'yes')
        if remove_thumbnail:
            if program.thumbnail_path:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], program.thumbnail_path)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass
            program.thumbnail_path = None
        elif 'thumbnail' in request.files and request.files['thumbnail'].filename:
            thumb_file = request.files['thumbnail']
            allowed_ext = {'jpg', 'jpeg', 'png', 'webp'}
            orig_name = thumb_file.filename
            ext = orig_name.rsplit('.', 1)[-1].lower() if '.' in orig_name else ''

            if ext not in allowed_ext:
                flash('Thumbnail must be JPG, PNG, or WEBP.', 'error')
                db.session.rollback()
                return render_template('programs/form.html', program=program)

            thumb_file.seek(0, os.SEEK_END)
            size = thumb_file.tell()
            thumb_file.seek(0)
            if size > 2 * 1024 * 1024:
                flash('Thumbnail file is too large. Maximum size is 2MB.', 'error')
                db.session.rollback()
                return render_template('programs/form.html', program=program)

            fname = secure_filename(f"program_{program.id}_{orig_name}")
            up_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'programs', str(program.id))
            os.makedirs(up_dir, exist_ok=True)
            path = os.path.join(up_dir, fname)
            thumb_file.save(path)

            if program.thumbnail_path and program.thumbnail_path != f"programs/{program.id}/{fname}":
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], program.thumbnail_path)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            program.thumbnail_path = f"programs/{program.id}/{fname}"

        db.session.commit()
        log_activity(log_act, entity_type="program", entity_id=program.id, details={"name": program.name})
        flash('Program scheme saved successfully.', 'success')
        return redirect(url_for('programs_list'))

    return render_template('programs/form.html', program=program)

@app.route('/api/farmers/search')
@login_required
def api_farmers_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    farmers = Farmer.query.filter(
        db.or_(Farmer.full_name.ilike(f"%{q}%"), Farmer.cnic.ilike(f"%{q}%"))
    ).limit(10).all()
    
    return jsonify([{
        'id': f.id,
        'full_name': f.full_name,
        'cnic': f.cnic,
        'farmer_id': f.farmer_id
    } for f in farmers])

@app.route('/programs/<int:program_id>/enroll-farmer', methods=['POST'])
@login_required
def api_program_enroll_farmer(program_id):
    if not current_user.has_perm('program_edit') or not current_user.has_perm('farmer_edit'):
        return jsonify({'error': 'Permission denied'}), 403
    
    program = Program.query.get_or_404(program_id)
    farmer_id = request.form.get('farmer_id', type=int)
    farmer = Farmer.query.get_or_404(farmer_id)
    
    existing = FarmerProgram.query.filter_by(farmer_id=farmer.id, program_id=program.id).first()
    if existing:
        return jsonify({'error': 'Farmer is already enrolled in this program'}), 400
        
    enrollment = FarmerProgram(
        farmer_id=farmer.id,
        program_id=program.id,
        enrolled_at=datetime.utcnow(),
        status='Active'
    )
    db.session.add(enrollment)
    db.session.flush()
    
    eq_ids = request.form.getlist('equipment_ids[]')
    for eq_id in eq_ids:
        eq = Equipment.query.filter_by(id=eq_id, program_id=program.id).first()
        if eq:
            govt_sub = eq.actual_price * (eq.subsidy_pct / 100)
            f_price = eq.actual_price - govt_sub
            fpe = FarmerProgramEquipment(
                farmer_program_id=enrollment.id,
                equipment_id=eq.id,
                actual_price=eq.actual_price,
                govt_subsidy_amount=govt_sub,
                farmer_price=f_price
            )
            db.session.add(fpe)
            
    db.session.commit()
    log_activity("Enrolled farmer in program via program management", entity_type="farmer_program", entity_id=enrollment.id)
    return jsonify({'success': True})

@app.route('/programs/<int:program_id>/enrollments/<int:enrollment_id>/status', methods=['POST'])
@login_required
def api_program_enrollment_status(program_id, enrollment_id):
    if not current_user.has_perm('program_edit'):
        return jsonify({'error': 'Permission denied'}), 403
        
    enrollment = FarmerProgram.query.filter_by(id=enrollment_id, program_id=program_id).first_or_404()
    status = request.form.get('status', '').strip()
    if status not in ['Active', 'Completed', 'Dropped']:
        return jsonify({'error': 'Invalid status'}), 400
        
    enrollment.status = status
    db.session.commit()
    log_activity("Updated enrollment status", entity_type="farmer_program", entity_id=enrollment.id, details={"status": status})
    return jsonify({'success': True})

@app.route('/programs/<int:program_id>/enrollments/<int:enrollment_id>/delete', methods=['POST'])
@login_required
def api_program_remove_farmer(program_id, enrollment_id):
    if not current_user.has_perm('program_edit'):
        return jsonify({'error': 'Permission denied'}), 403
        
    enrollment = FarmerProgram.query.filter_by(id=enrollment_id, program_id=program_id).first_or_404()
    db.session.delete(enrollment)
    db.session.commit()
    log_activity("Removed farmer from program", entity_type="farmer_program", entity_id=enrollment_id)
    return jsonify({'success': True})

@app.route('/programs/<int:id>/gallery', methods=['GET', 'POST'])
@login_required
def program_gallery(id):
    if not current_user.has_perm('program_view'):
        flash('Permission denied.', 'error')
        return redirect(url_for('dashboard'))

    program = Program.query.get_or_404(id)
    track_progress('program_gallery', entity_type='program', entity_id=program.id)

    if request.method == 'POST':
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            orig_name = secure_filename(file.filename)
            up_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'programs', str(program.id), 'gallery')
            os.makedirs(up_dir, exist_ok=True)
            
            fpath = os.path.join(up_dir, orig_name)
            file.save(fpath)

            size_bytes = os.path.getsize(fpath)
            mime_type = get_file_mime(fpath)

            file_type = 'document'
            if mime_type.startswith('image/'): file_type = 'image'
            elif mime_type.startswith('video/'): file_type = 'video'
            elif mime_type.startswith('audio/'): file_type = 'audio'

            rel_path = f"programs/{program.id}/gallery/{orig_name}"
            thumb_rel = None
            if file_type == 'image':
                tname = f"thumb_{orig_name}"
                tpath = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', tname)
                if generate_thumbnail(fpath, tpath):
                    thumb_rel = f"thumbnails/{tname}"

            media = GalleryMedia(
                scope='program',
                program_id=program.id,
                file_path=rel_path,
                thumb_path=thumb_rel,
                mime_type=mime_type,
                file_type=file_type,
                original_name=orig_name,
                size_bytes=size_bytes,
                uploaded_by=current_user.id
            )
            db.session.add(media)
            db.session.commit()
            log_activity("Uploaded media to program gallery", entity_type="gallery_media", entity_id=media.id)
            flash('Media uploaded to program gallery.', 'success')

    filter_type = request.args.get('type', 'all')
    sort_order = request.args.get('sort', 'newest')

    query = GalleryMedia.query.filter_by(scope='program', program_id=program.id)
    if filter_type != 'all':
        query = query.filter_by(file_type=filter_type)

    if sort_order == 'oldest':
        query = query.order_by(GalleryMedia.uploaded_at.asc())
    elif sort_order == 'name':
        query = query.order_by(GalleryMedia.original_name.asc())
    else:
        query = query.order_by(GalleryMedia.uploaded_at.desc())

    media_items = query.all()
    return render_template('programs/gallery.html', program=program, media_items=media_items, filter_type=filter_type, sort_order=sort_order)

# ---- LOGS ROUTE ----
@app.route('/logs')
@login_required
def logs_view():
    if not current_user.has_perm('logs_access'):
        flash('Permission denied. Admin access required.', 'error')
        return redirect(url_for('dashboard'))

    track_progress('logs_view')
    employee_search = request.args.get('employee', '').strip()
    action_search = request.args.get('action', '').strip()

    query = Log.query
    if employee_search:
        query = query.join(User).filter(User.full_name.ilike(f"%{employee_search}%"))
    if action_search:
        query = query.filter(Log.action.ilike(f"%{action_search}%"))

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Log.created_at.desc()).paginate(page=page, per_page=50, error_out=False)

    return render_template('logs.html', pagination=pagination, employee_search=employee_search, action_search=action_search)

@app.route('/logs/export')
@login_required
def logs_export():
    if current_user.role != 'superadmin':
        flash('SuperAdmin access required for export.', 'error')
        return redirect(url_for('logs_view'))

    logs = Log.query.order_by(Log.created_at.desc()).all()
    output = "ID,User,Action,Entity Type,Entity ID,IP Address,PKT Timestamp\n"
    for l in logs:
        uname = l.user.full_name if l.user else 'System'
        pkt_time_str = pkt_time_filter(l.created_at)
        output += f'"{l.id}","{uname}","{l.action}","{l.entity_type or ""}","{l.entity_id or ""}","{l.ip_address}","{pkt_time_str}"\n'

    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=aeportal_logs.csv"})

# ---- USERS ROUTES (SuperAdmin Only) ----
@app.route('/users')
@login_required
def users_list():
    if not current_user.has_perm('user_mgmt'):
        flash('SuperAdmin access required for user management.', 'error')
        return redirect(url_for('dashboard'))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users/list.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@app.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def user_form(id=None):
    if not current_user.has_perm('user_mgmt'):
        flash('SuperAdmin access required.', 'error')
        return redirect(url_for('dashboard'))

    target_user = User.query.get_or_404(id) if id else None
    
    if target_user and target_user.email in ['umar@atechabad.com', 'naem@atechabad.com'] and current_user.role != 'superadmin':
        flash('Cannot edit seed administrator account.', 'error')
        return redirect(url_for('users_list'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'staff')
        password = request.form.get('password', '')

        perms = {
            "farmer_view": 1 if 'perm_farmer_view' in request.form else 0,
            "farmer_edit": 1 if 'perm_farmer_edit' in request.form else 0,
            "farmer_delete": 1 if 'perm_farmer_delete' in request.form else 0,
            "program_view": 1 if 'perm_program_view' in request.form else 0,
            "program_edit": 1 if 'perm_program_edit' in request.form else 0,
            "program_delete": 1 if 'perm_program_delete' in request.form else 0,
            "logs_access": 1 if 'perm_logs_access' in request.form else 0,
            "gallery_access": request.form.get('perm_gallery_access', 'none'),
            "user_mgmt": 1 if 'perm_user_mgmt' in request.form else 0
        }

        if not target_user:
            target_user = User(
                full_name=full_name,
                email=email,
                role=role,
                permissions=json.dumps(perms),
                is_active=True
            )
            if password:
                target_user.set_password(password)
            else:
                target_user.set_password("TempPass@123")
            db.session.add(target_user)
            log_act = "Created user account"
        else:
            target_user.full_name = full_name
            target_user.email = email
            target_user.role = role
            target_user.permissions = json.dumps(perms)
            if password:
                target_user.set_password(password)
            log_act = "Updated user account"

        db.session.commit()
        log_activity(log_act, entity_type="user", entity_id=target_user.id, details={"email": email, "role": role})
        flash('User saved successfully.', 'success')
        return redirect(url_for('users_list'))

    return render_template('users/form.html', target_user=target_user)

@app.route('/users/<int:id>/delete', methods=['POST'])
@login_required
def user_delete(id):
    if not current_user.has_perm('user_mgmt'):
        flash('SuperAdmin access required.', 'error')
        return redirect(url_for('dashboard'))

    target_user = User.query.get_or_404(id)
    if target_user.email in ['umar@atechabad.com', 'naem@atechabad.com']:
        flash('Seed administrator accounts cannot be deleted.', 'error')
        return redirect(url_for('users_list'))

    db.session.delete(target_user)
    db.session.commit()
    log_activity("Deleted user account", entity_type="user", entity_id=id)
    flash("User account deleted.", 'success')
    return redirect(url_for('users_list'))

# ---- EXCLUSIVE GALLERY ROUTE ----
@app.route('/exclusive-gallery', methods=['GET', 'POST'])
@login_required
def exclusive_gallery():
    gallery_perm = current_user.get_perms().get('gallery_access', 'none')
    if current_user.role == 'superadmin':
        gallery_perm = 'super'

    if gallery_perm == 'none':
        flash('Permission denied. Exclusive Gallery access required.', 'error')
        return redirect(url_for('dashboard'))

    track_progress('exclusive_gallery')

    if request.method == 'POST':
        if gallery_perm != 'super' and current_user.role != 'superadmin':
            flash('Only Super access users can upload to Exclusive Gallery.', 'error')
            return redirect(url_for('exclusive_gallery'))

        uploaded_files = []
        for key in request.files:
            uploaded_files.extend(request.files.getlist(key))

        success_count = 0
        up_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'exclusive')
        os.makedirs(up_dir, exist_ok=True)

        for file in uploaded_files:
            if not file or not file.filename:
                continue

            orig_name = secure_filename(file.filename)
            if not orig_name:
                continue

            unique_name, fpath = get_unique_filename(up_dir, orig_name)
            file.save(fpath)

            if orig_name.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(fpath, 'r') as zip_ref:
                        extract_dir = os.path.join(up_dir, f"zip_{int(datetime.utcnow().timestamp())}")
                        zip_ref.extractall(extract_dir)
                        for root, _, files in os.walk(extract_dir):
                            for fname in files:
                                zf_path = os.path.join(root, fname)
                                zf_mime = get_file_mime(zf_path)
                                zf_type = 'document'
                                if zf_mime.startswith('image/'): zf_type = 'image'
                                elif zf_mime.startswith('video/'): zf_type = 'video'
                                elif zf_mime.startswith('audio/'): zf_type = 'audio'

                                rel_zpath = os.path.relpath(zf_path, app.config['UPLOAD_FOLDER']).replace('\\', '/')
                                db.session.add(GalleryMedia(
                                    scope='exclusive',
                                    file_path=rel_zpath,
                                    mime_type=zf_mime,
                                    file_type=zf_type,
                                    original_name=fname,
                                    size_bytes=os.path.getsize(zf_path),
                                    uploaded_by=current_user.id
                                ))
                                success_count += 1
                    db.session.commit()
                    log_activity("Extracted zip to Exclusive Gallery", entity_type="exclusive_gallery")
                except Exception as e:
                    flash(f'Error processing zip file {orig_name}: {e}', 'error')
            else:
                size_bytes = os.path.getsize(fpath)
                mime_type = get_file_mime(fpath)

                file_type = 'document'
                if mime_type.startswith('image/'): file_type = 'image'
                elif mime_type.startswith('video/'): file_type = 'video'
                elif mime_type.startswith('audio/'): file_type = 'audio'

                rel_path = f"exclusive/{unique_name}"
                thumb_rel = None
                if file_type == 'image':
                    tname = f"thumb_ex_{unique_name}"
                    tpath = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', tname)
                    if generate_thumbnail(fpath, tpath):
                        thumb_rel = f"thumbnails/{tname}"

                media = GalleryMedia(
                    scope='exclusive',
                    file_path=rel_path,
                    thumb_path=thumb_rel,
                    mime_type=mime_type,
                    file_type=file_type,
                    original_name=orig_name,
                    size_bytes=size_bytes,
                    uploaded_by=current_user.id
                )
                db.session.add(media)
                success_count += 1

        if success_count > 0:
            db.session.commit()
            log_activity(f"Uploaded {success_count} media file(s) to Exclusive Gallery", entity_type="exclusive_gallery")
            flash(f"Successfully uploaded {success_count} file(s) to Exclusive Gallery.", 'success')

    filter_type = request.args.get('type', 'all')
    search = request.args.get('search', '').strip()
    sort_order = request.args.get('sort', 'newest')

    query = GalleryMedia.query.filter_by(scope='exclusive')
    if filter_type != 'all':
        query = query.filter_by(file_type=filter_type)
    if search:
        query = query.filter(GalleryMedia.original_name.ilike(f"%{search}%"))

    if sort_order == 'oldest':
        query = query.order_by(GalleryMedia.uploaded_at.asc())
    elif sort_order == 'name':
        query = query.order_by(GalleryMedia.original_name.asc())
    else:
        query = query.order_by(GalleryMedia.uploaded_at.desc())

    media_items = query.all()
    return render_template('gallery_exclusive.html',
        media_items=media_items,
        filter_type=filter_type,
        search=search,
        sort_order=sort_order,
        gallery_perm=gallery_perm
    )

@app.route('/exclusive-gallery/<int:id>/delete', methods=['POST'])
@login_required
def exclusive_gallery_delete(id):
    gallery_perm = current_user.get_perms().get('gallery_access', 'none')
    if current_user.role != 'superadmin' and gallery_perm != 'super':
        flash('Only Super access users can delete gallery items.', 'error')
        return redirect(url_for('exclusive_gallery'))

    media = GalleryMedia.query.get_or_404(id)
    db.session.delete(media)
    db.session.commit()
    log_activity("Deleted Exclusive Gallery media", entity_type="gallery_media", entity_id=id)
    flash('Gallery item deleted.', 'success')
    return redirect(url_for('exclusive_gallery'))

# ---- SERVE UPLOADED MEDIA ----
@app.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Local dev server runs when executed directly; cPanel uses passenger_wsgi.py
    app.run(host='127.0.0.1', port=5001, debug=True)
