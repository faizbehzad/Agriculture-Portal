import os
import sys
import json
from datetime import datetime

# Load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def init_db():
    print("Initializing Agricultural Engineering Portal Database...")
    
    # Ensure directory structure exists
    dirs = [
        'uploads',
        'uploads/farmers',
        'uploads/programs',
        'uploads/exclusive',
        'uploads/thumbnails',
        'logs'
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"Directory ensured: {d}")

    # Setup database connection string
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_name = os.environ.get('DB_NAME', '')
    db_user = os.environ.get('DB_USER', '')
    db_pass = os.environ.get('DB_PASS', '')

    if db_name and db_user:
        # MySQL/MariaDB PyMySQL driver
        db_uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}?charset=utf8mb4"
    else:
        # SQLite fallback for local development testing
        db_path = os.path.join(os.path.dirname(__file__), 'aeportal.db')
        db_uri = f"sqlite:///{db_path}"
        print(f"Using SQLite database for local fallback: {db_path}")

    os.environ['SQLALCHEMY_DATABASE_URI'] = db_uri

    # Import app and db models from aeportal
    try:
        from aeportal import app, db, User, ProgramColorRotation
        with app.app_context():
            db.create_all()
            print("Database schema created successfully.")

            # Seed Program Color Rotation
            colors = [
                ('#2F7A4C', 'Forest Leaf'),
                ('#1B4D33', 'Deep Forest'),
                ('#D9A62E', 'Harvest Amber'),
                ('#2E6B9E', 'River Blue'),
                ('#8E44AD', 'Orchid Purple'),
                ('#D35400', 'Terracotta'),
                ('#16A085', 'Teal Green'),
                ('#C0392B', 'Brick Red'),
                ('#2C3E50', 'Slate Navy'),
                ('#7F8C8D', 'Mountain Gray')
            ]
            for hex_val, c_name in colors:
                existing = ProgramColorRotation.query.filter_by(color_hex=hex_val).first()
                if not existing:
                    db.session.add(ProgramColorRotation(color_hex=hex_val, color_name=c_name, is_used=False))
            db.session.commit()
            print("Program color rotation seeded.")

            # Seed SuperAdmin & Default Admin
            superadmin_email = os.environ.get('SUPERADMIN_EMAIL', 'umar@atechabad.com')
            default_admin_email = os.environ.get('DEFAULT_ADMIN_EMAIL', 'naem@atechabad.com')

            super_user = User.query.filter_by(email=superadmin_email).first()
            if not super_user:
                full_perms = {
                    "farmer_view": 1, "farmer_edit": 1, "farmer_delete": 1,
                    "program_view": 1, "program_edit": 1, "program_delete": 1,
                    "logs_access": 1, "gallery_access": "super", "user_mgmt": 1
                }
                super_user = User(
                    full_name="Umar (SuperAdmin)",
                    email=superadmin_email,
                    role="superadmin",
                    permissions=json.dumps(full_perms),
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                super_user.set_password("Admin@123456")
                db.session.add(super_user)
                print(f"SuperAdmin account created: {superadmin_email} / Admin@123456")

            admin_user = User.query.filter_by(email=default_admin_email).first()
            if not admin_user:
                admin_perms = {
                    "farmer_view": 1, "farmer_edit": 1, "farmer_delete": 1,
                    "program_view": 1, "program_edit": 1, "program_delete": 1,
                    "logs_access": 1, "gallery_access": "super", "user_mgmt": 0
                }
                admin_user = User(
                    full_name="Naeem (Admin)",
                    email=default_admin_email,
                    role="admin",
                    permissions=json.dumps(admin_perms),
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                admin_user.set_password("Admin@123456")
                db.session.add(admin_user)
                print(f"Default Admin account created: {default_admin_email} / Admin@123456")

            db.session.commit()
            print("Initialization completed successfully!")
    except Exception as e:
        print(f"Error during initialization: {e}", file=sys.stderr)
        raise e

if __name__ == '__main__':
    init_db()
