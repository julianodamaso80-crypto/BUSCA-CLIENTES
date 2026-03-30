"""
WSGI config for core project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()

# Run migrations and collectstatic on Vercel deploy
if os.environ.get('VERCEL'):
    from django.core.management import call_command
    try:
        call_command('migrate', '--noinput')
    except Exception:
        pass
