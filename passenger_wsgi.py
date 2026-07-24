import sys, os

# Ensure the app directory is in the path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# Load .env file BEFORE importing the app so all env vars are available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(app_dir, '.env'))
except ImportError:
    pass

from aeportal import app as application
