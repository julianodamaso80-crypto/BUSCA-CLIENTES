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
        admin_email = 'julianodamaso80@gmail.com'
        admin_password = os.environ.get('ADMIN_PASSWORD', '160807')
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email=admin_email,
                password=admin_password,
            )
        else:
            # Atualiza email e senha do admin existente
            admin_user = User.objects.get(username='admin')
            if admin_user.email != admin_email:
                admin_user.email = admin_email
                admin_user.set_password(admin_password)
                admin_user.save()
    except Exception as e:
        print(f'Superuser error: {e}')
