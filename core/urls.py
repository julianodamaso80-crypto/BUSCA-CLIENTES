from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect


def redirect_to_dashboard(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


urlpatterns = [
    # Raiz redireciona para dashboard ou login
    path('', redirect_to_dashboard, name='home'),

    # Autenticação
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Apps
    path('dashboard/', include('clientes.urls')),
    path('disparo/', include('disparo.urls')),

    # Admin
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += [
        path('__reload__/', include('django_browser_reload.urls')),
    ]
