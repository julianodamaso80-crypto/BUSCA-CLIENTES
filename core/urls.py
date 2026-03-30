import os

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.views.generic import TemplateView

IS_VERCEL = os.getenv('VERCEL', '') == '1'


def redirect_to_dashboard(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('landing')


urlpatterns = [
    # Landing page publica
    path('', TemplateView.as_view(template_name='landing.html'), name='landing'),

    # Autenticacao
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Apps
    path('dashboard/', include('clientes.urls')),

    # Admin
    path('admin/', admin.site.urls),
]

# disparo e aquecimento dependem de openai e Evolution API
# que nao estao disponiveis no ambiente serverless da Vercel
if not IS_VERCEL:
    urlpatterns += [
        path('disparo/', include('disparo.urls')),
        path('aquecimento/', include('aquecimento.urls')),
    ]

if settings.DEBUG and not IS_VERCEL:
    try:
        urlpatterns += [
            path('__reload__/', include('django_browser_reload.urls')),
        ]
    except Exception:
        pass
