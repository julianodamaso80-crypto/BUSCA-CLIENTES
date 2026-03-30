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
    try:
        call_command('collectstatic', '--noinput')
    except Exception:
        pass

    # Create superuser if it doesn't exist
    try:
        from django.contrib.auth.models import User
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@buscaleads.site',
                password=os.environ.get('ADMIN_PASSWORD', 'BuscaLeads2026!')
            )
    except Exception:
        pass
