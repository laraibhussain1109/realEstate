"""Copy into the WSGI file selected by PythonAnywhere's Web tab.

Replace YOUR_USERNAME and REPOSITORY_DIRECTORY. Select the matching Python
version/virtualenv in the Web tab. Keep .env readable only by your account.
"""
import os
import sys
from pathlib import Path

project_root = Path('/home/YOUR_USERNAME/REPOSITORY_DIRECTORY')
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', override=False)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
