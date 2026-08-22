"""
create_user.py — Create or update a user (superadmin/admin/staff) via code.

Usage (run via SSH from the app root, same place you run init.py):

    python create_user.py --email umar@atechabad.com --name "Umar" --role superadmin --password "SomeStrongPass1!"
    python create_user.py --email jane@atechabad.com --name "Jane Doe" --role staff --password "TempPass!23" --template staff
    python create_user.py --email umar@atechabad.com --password "NewPass!23"   # just reset password, keep role/perms

If --password is omitted, you'll be prompted for one (hidden input) so it
never ends up in shell history.

Roles: superadmin | admin | staff | custom
Permission templates (--template): viewer | staff | admin | full
  (only applied when creating a NEW user, or when --template is explicitly
  passed for an existing user)
"""

import os
import sys
import json
import argparse
import getpass

# Load .env before importing the app, same as passenger_wsgi.py / init.py
basedir = os.path.dirname(os.path.abspath(__file__))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(basedir, '.env'))
except ImportError:
    pass

from aeportal import app, db, User

TEMPLATES = {
    "viewer": {
        "farmer_view": 1, "farmer_edit": 0, "farmer_delete": 0,
        "program_view": 1, "program_edit": 0, "program_delete": 0,
        "logs_access": 0, "gallery_access": "none", "user_mgmt": 0
    },
    "staff": {
        "farmer_view": 1, "farmer_edit": 1, "farmer_delete": 0,
        "program_view": 1, "program_edit": 0, "program_delete": 0,
        "logs_access": 0, "gallery_access": "none", "user_mgmt": 0
    },
    "admin": {
        "farmer_view": 1, "farmer_edit": 1, "farmer_delete": 1,
        "program_view": 1, "program_edit": 1, "program_delete": 1,
        "logs_access": 1, "gallery_access": "super", "user_mgmt": 0
    },
    "full": {
        "farmer_view": 1, "farmer_edit": 1, "farmer_delete": 1,
        "program_view": 1, "program_edit": 1, "program_delete": 1,
        "logs_access": 1, "gallery_access": "super", "user_mgmt": 1
    },
}


def main():
    parser = argparse.ArgumentParser(description="Create or update an AE Portal user.")
    parser.add_argument("--email", required=True, help="User's login email")
    parser.add_argument("--name", help="Full name (required when creating a new user)")
    parser.add_argument("--role", choices=["superadmin", "admin", "staff", "custom"],
                         help="Role to assign (required when creating a new user)")
    parser.add_argument("--password", help="Plaintext password (omit to be prompted securely)")
    parser.add_argument("--template", choices=list(TEMPLATES.keys()),
                         help="Permission template to apply (viewer/staff/admin/full)")
    parser.add_argument("--deactivate", action="store_true", help="Set is_active=False")
    parser.add_argument("--activate", action="store_true", help="Set is_active=True")
    args = parser.parse_args()

    with app.app_context():
        db.create_all()  # safe no-op if tables already exist

        user = User.query.filter_by(email=args.email).first()
        creating = user is None

        if creating:
            if not args.name or not args.role:
                print("Error: --name and --role are required when creating a new user.", file=sys.stderr)
                sys.exit(1)

        password = args.password
        if not password:
            password = getpass.getpass(f"Enter password for {args.email}: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: passwords do not match.", file=sys.stderr)
                sys.exit(1)
        if len(password) < 8:
            print("Error: password must be at least 8 characters.", file=sys.stderr)
            sys.exit(1)

        # Work out permissions
        template_key = args.template
        if creating and not template_key:
            # sensible default template per role
            template_key = "full" if args.role == "superadmin" else (
                "admin" if args.role == "admin" else "staff"
            )
        perms = TEMPLATES[template_key] if template_key else None

        if creating:
            user = User(
                full_name=args.name,
                email=args.email,
                role=args.role,
                permissions=json.dumps(perms),
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            action = "Created"
        else:
            if args.name:
                user.full_name = args.name
            if args.role:
                user.role = args.role
            if perms is not None:
                user.permissions = json.dumps(perms)
            user.set_password(password)
            if args.deactivate:
                user.is_active = False
            if args.activate:
                user.is_active = True
            action = "Updated"

        db.session.commit()
        print(f"{action} user: {user.email} (role={user.role}, active={user.is_active})")
        print("Permissions:", user.permissions)


if __name__ == "__main__":
    main()
