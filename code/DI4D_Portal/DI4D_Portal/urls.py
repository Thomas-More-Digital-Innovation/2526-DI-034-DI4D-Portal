"""
URL configuration for DI4D_Portal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from DI4D_app import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Broker provider logout override: ensure our provider logout clears the Django session
    path('openid/logout/', views.provider_logout, name='provider_logout'),
    path('openid/debug/', views.debug_oidc_settings, name='debug_oidc_settings'),
    path('openid/session_debug/', views.session_debug, name='session_debug'),
    path('openid/', include('oidc_provider.urls', namespace='oidc_provider')),
    # Override the default mozilla-django-oidc callback so we can capture id_token into the session
    path('oidc/callback/', views.CustomOIDCAuthenticationCallbackView.as_view(), name='oidc_callback_override'),
    # Also accept the Common 'login/callback/' redirect some clients use
    path('login/callback/', views.CustomOIDCAuthenticationCallbackView.as_view(), name='oidc_callback_override_login'),
    # Provide a quick prompt-login redirect to Keycloak to force login screen (avoid 'already authenticated' broker error)
    path('oidc/prompt_login/', views.oidc_prompt_login, name='oidc_prompt_login'),
    path('oidc/', include('mozilla_django_oidc.urls')),
    path('test', views.hello_world, name='hello_world'),
    path('', views.home, name='home'),
    path('accounts/login/', views.login_view, name='accounts_login'),
    path('login/', include('mozilla_django_oidc.urls')),
    path('student_registration/', views.student_registration, name='student_registration'),
    path('news/', views.news, name='news'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.settings, name='settings'),

    # Docs : https://docs.djangoproject.com/en/6.0/topics/auth/default/#all-authentication-views
    path("password_reset/", auth_views.PasswordResetView.as_view(
        template_name="auth/forgot_password.jinja"
    ), name="password_reset"),
    path("password_reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="auth/reset_send.jinja"
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="auth/reset_password.jinja"
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="auth/reset_complete.jinja"
    ), name="password_reset_complete"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
