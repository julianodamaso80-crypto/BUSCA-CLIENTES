"""
WSGI config for core project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()

# Run setup tasks on Vercel deploy
if os.environ.get('VERCEL'):
    from django.core.management import call_command

    # 1. Run migrations
    try:
        call_command('migrate', '--noinput')
    except Exception as e:
        print(f'Migration error: {e}')

    # 2. Populate estados and cidades
    try:
        from clientes.models import Estado
        if Estado.objects.count() == 0:
            call_command('popular_localizacoes')
    except Exception as e:
        print(f'Popular localizacoes error: {e}')

    # 3. Create superuser if not exists
    try:
        from django.contrib.auth.models import User
        admin_username = 'julianodamaso80@gmail.com'
        admin_password = os.environ.get('ADMIN_PASSWORD', '160807')
        # Remove admin antigo se existir
        User.objects.filter(username='admin').exclude(username=admin_username).delete()
        if not User.objects.filter(username=admin_username).exists():
            User.objects.create_superuser(
                username=admin_username,
                email=admin_username,
                password=admin_password,
            )
        else:
            user = User.objects.get(username=admin_username)
            user.set_password(admin_password)
            user.save()
    except Exception as e:
        print(f'Superuser error: {e}')
