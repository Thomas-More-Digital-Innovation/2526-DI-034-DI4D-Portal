from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth import authenticate, login
from .models import ApplicationSetting, News, User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.urls import reverse
from urllib.parse import urlencode
from django.core.paginator import Paginator
import logging

logger = logging.getLogger('DI4D_app')
from django.db.models import Q
from django.contrib.auth import update_session_auth_hash

# Create your views here.
def hello_world(request):
    return render(request, 'test.jinja')


def provider_logout(request):
    """Endpoint intended to be used as the brokered provider logout target.

    When Keycloak redirects the browser here after its end-session, this view
    ensures the Django session (identity-provider session) is cleared and then
    redirects to the `next` parameter (or `home`).
    """
    # Clear any local session/cookies
    logout(request)
    next_url = request.GET.get('next') or 'home'
    return redirect(next_url)


def debug_oidc_settings(request):
    """Return current OIDC-related settings for debugging."""
    import os
    import importlib
    try:
        settings_module = importlib.import_module(os.environ.get('DJANGO_SETTINGS_MODULE'))
        settings_file = getattr(settings_module, '__file__', None)
    except Exception:
        settings_file = None

    env_oidc = {k: v for k, v in os.environ.items() if k.startswith('OIDC')}
    data = {
        'DJANGO_SETTINGS_MODULE': os.environ.get('DJANGO_SETTINGS_MODULE'),
        'SETTINGS_FILE': settings_file,
        'ENV_OIDC_VARS': env_oidc,
        'OIDC_ISSUER': getattr(settings, 'OIDC_ISSUER', None),
        'OIDC_OP_AUTHORIZATION_ENDPOINT': getattr(settings, 'OIDC_OP_AUTHORIZATION_ENDPOINT', None),
        'OIDC_OP_LOGOUT_ENDPOINT': getattr(settings, 'OIDC_OP_LOGOUT_ENDPOINT', None),
        'OIDC_STORE_ID_TOKEN': getattr(settings, 'OIDC_STORE_ID_TOKEN', None),
    }
    return HttpResponse('\n'.join(f"{k}={v}" for k, v in data.items()), content_type='text/plain')


def session_debug(request):
    """Show relevant session keys and their values for debugging OIDC tokens."""
    lines = []
    for k, v in request.session.items():
        if any(substr in k.lower() for substr in ('id', 'token', 'oidc')):
            val = v
            # Avoid dumping huge secrets fully
            if isinstance(val, str) and len(val) > 200:
                val = val[:100] + '...' + val[-50:]
            lines.append(f"{k}={val}")
    lines.append('')
    lines.append('ALL_KEYS=' + ','.join(request.session.keys()))
    return HttpResponse('\n'.join(lines), content_type='text/plain')


# Hook into mozilla-django-oidc callback to make sure id_token ends up in session
import requests
import os
try:
    from mozilla_django_oidc.views import OIDCAuthenticationCallbackView
except Exception:
    OIDCAuthenticationCallbackView = None


class CustomOIDCAuthenticationCallbackView(OIDCAuthenticationCallbackView if OIDCAuthenticationCallbackView else object):
    def dispatch(self, request, *args, **kwargs):
        logger.info("CustomOIDCAuthenticationCallbackView called")

        # If possible, do a direct token exchange using the authorization code to capture id_token
        try:
            code = request.GET.get('code')
            if code and not request.session.get('oidc_id_token'):
                token_endpoint = getattr(settings, 'OIDC_OP_TOKEN_ENDPOINT', None) or os.environ.get('OIDC_OP_TOKEN_ENDPOINT')
                client_id = getattr(settings, 'OIDC_RP_CLIENT_ID', None) or os.environ.get('OIDC_RP_CLIENT_ID')
                client_secret = getattr(settings, 'OIDC_RP_CLIENT_SECRET', None) or os.environ.get('OIDC_RP_CLIENT_SECRET')
                if token_endpoint and client_id and client_secret:
                    redirect_uri = request.build_absolute_uri()
                    payload = {
                        'grant_type': 'authorization_code',
                        'code': code,
                        'redirect_uri': redirect_uri,
                    }
                    # Use HTTP Basic auth as recommended by OAuth2
                    resp = requests.post(token_endpoint, data=payload, auth=(client_id, client_secret), timeout=5)
                    if resp.ok:
                        j = resp.json()
                        id_token = j.get('id_token')
                        if id_token:
                            request.session['oidc_id_token'] = id_token
                            logger.info("Custom callback: fetched id_token from token endpoint and stored in session")
                    else:
                        logger.warning('Token endpoint responded with status %s: %s', resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.exception("Custom callback token exchange failed: %s", exc)

        # Let the library process authentication (it may store tokens itself)
        response = super().dispatch(request, *args, **kwargs)
        logger.info("After super().dispatch, session keys: %s", list(request.session.keys()))

        # Attempt to extract id_token from session structures and store it under a well-known key
        if not request.session.get('oidc_id_token'):
            oidc_auth = request.session.get('oidc_auth') or request.session.get('oidc')
            if isinstance(oidc_auth, dict):
                id_token = oidc_auth.get('id_token') or oidc_auth.get('idToken') or oidc_auth.get('idTokenHint')
                if id_token:
                    request.session['oidc_id_token'] = id_token
                    logger.info("CustomOIDCAuthenticationCallbackView: stored oidc_id_token in session (post-lib)")
            # Some implementations put id_token directly as 'id_token' in the session
            if request.session.get('id_token'):
                request.session['oidc_id_token'] = request.session.get('id_token')
        logger.info("Final session keys: %s", list(request.session.keys()))
        return response

def home(request):
    data = {}
    today = timezone.now().date() 
    # Check if user is already logged in
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Check if there is a form send
    if request.method == "POST":
        # Get data from form
        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")
        
        # Get mails of admins
        admin_emails = User.objects.filter(userTypeId__name='admin').values_list('email', flat=True)
        # if everything is filled in
        if name and email and message:
            # Send email via SMTP
            if len(admin_emails) > 0:
                result = send_mail(
                    subject=f"Contact Form DI4D Portal - Message from {name}",
                    message=f"Name : {name}\nEmail: {email}\nMessage:\n{message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=False
                )
                if result:
                    data["success"] = "Your message has been sent successfully."
                else:
                    data["error"] = "There was an error sending your message. Please try again later."

    # Check if student can register himself
    application_setting = ApplicationSetting.objects.first()
    if application_setting and application_setting.startDate <= today <= application_setting.endDate:
        data["register"] = True
    else:
        data["register"] = False

    # If there is an application setting, give start and end date
    if application_setting:
        data["startDate"] = application_setting.startDate.strftime('%B %d, %Y')
        data["endDate"] = application_setting.endDate.strftime('%B %d, %Y')
    
    # Get news articles (- : for latest news articles, then we limit to 2 articles)
    data["news"] = News.objects.filter(isPublic=True).order_by('-lastEditDate')[:2]

    return render(request, 'public/home.jinja',  data)


def logout_view(request):
    """Clear local session and redirect the browser to Keycloak end-session endpoint.

    We try to fetch an ID token stored in session by mozilla-django-oidc (stored when
    OIDC_STORE_ID_TOKEN = True). If not present, we still redirect to Keycloak logout
    which will clear the Keycloak session cookie.
    """
    # Try several common session keys for the id_token
    id_token = None
    # mozilla-django-oidc stores it under 'oidc_id_token' when enabled
    id_token = request.session.get('oidc_id_token') or request.session.get('id_token')
    # some integrations keep tokens under an 'oidc_auth' dict
    if not id_token:
        oidc_auth = request.session.get('oidc_auth') or request.session.get('oidc')
        if isinstance(oidc_auth, dict):
            id_token = oidc_auth.get('id_token') or oidc_auth.get('idToken')

    # Log out of Django first (this will clear local session and any provider login state)
    logger.info("logout_view called; id_token_present=%s", bool(id_token))
    # Capture id_token before clearing session so we can pass it to Keycloak
    id_token_hint = id_token

    # Capture Django username before clearing session so we can find corresponding Keycloak user
    django_username = getattr(request.user, 'username', None)

    # Attempt to terminate Keycloak sessions by searching users by username via Admin API, I know this is REALLY dumb, but Keycloak doesn't provide a better way to do this
    try:
        kc_admin_user = os.getenv('KEYCLOAK_ADMIN_USER') or os.getenv('KC_BOOTSTRAP_ADMIN_USERNAME')
        kc_admin_pass = os.getenv('KEYCLOAK_ADMIN_PASSWORD') or os.getenv('KC_BOOTSTRAP_ADMIN_PASSWORD')
        kc_admin_base = os.getenv('KEYCLOAK_ADMIN_BASE') or os.getenv('KC_ADMIN_BASE') or 'http://localhost:8080'
        if django_username and kc_admin_user and kc_admin_pass:
            # Obtain admin access token from master realm
            token_url = f"{kc_admin_base}/realms/master/protocol/openid-connect/token"
            resp = requests.post(token_url, data={
                'grant_type': 'password',
                'client_id': 'admin-cli',
                'username': kc_admin_user,
                'password': kc_admin_pass,
            }, timeout=5)
            if resp.ok:
                admin_token = resp.json().get('access_token')
                # Find Keycloak user(s) with matching username
                users_url = f"{kc_admin_base}/admin/realms/di4d/users?username={django_username}"
                r_users = requests.get(users_url, headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
                if r_users.ok:
                    users = r_users.json()
                    logger.info('Found %d Keycloak users for username=%s', len(users), django_username)
                    for u in users:
                        kc_user_id = u.get('id')
                        if kc_user_id:
                            # Terminate sessions
                            logout_api = f"{kc_admin_base}/admin/realms/di4d/users/{kc_user_id}/logout"
                            r2 = requests.post(logout_api, headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
                            logger.info('Admin logout API for user %s response: %s %s', kc_user_id, r2.status_code, r2.text[:200])
                            # Attempt to unlink federated identity (so a different external identity can be linked later)
                            try:
                                delete_fed = requests.delete(f"{kc_admin_base}/admin/realms/di4d/users/{kc_user_id}/federated-identity/django-oidc", headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
                                if delete_fed.status_code in (200, 204):
                                    logger.info('Unlinked federated identity for user %s', kc_user_id)
                                elif delete_fed.status_code == 404:
                                    logger.info('No federated identity to unlink for user %s', kc_user_id)
                                else:
                                    logger.warning('Unlink federated identity response for user %s: %s %s', kc_user_id, delete_fed.status_code, delete_fed.text[:200])
                            except Exception:
                                logger.exception('Failed to unlink federated identity for user %s', kc_user_id)
                else:
                    logger.warning('Failed to search Keycloak users: %s %s', r_users.status_code, r_users.text[:200])
            else:
                logger.warning('Failed to obtain Keycloak admin token: %s %s', resp.status_code, resp.text[:200])
    except Exception:
        logger.exception('Failed to call Keycloak admin logout API')

    logout(request)

    # Build logout redirect to Keycloak (end session)
    logout_endpoint = getattr(settings, 'OIDC_OP_LOGOUT_ENDPOINT', None)
    # Fallback to environment or construct from issuer if settings doesn't expose it
    if not logout_endpoint:
        logout_endpoint = os.environ.get('OIDC_OP_LOGOUT_ENDPOINT')
    if not logout_endpoint:
        # prefer an explicit OIDC_OP_LOGOUT_ENDPOINT env var for Keycloak
        logout_endpoint = os.environ.get('OIDC_OP_LOGOUT_ENDPOINT') or 'http://localhost:8080/realms/di4d/protocol/openid-connect/logout'

    from urllib.parse import urlencode
    params = {}
    if id_token_hint:
        params['id_token_hint'] = id_token_hint
    else:
        # When id_token isn't available, include client_id to allow post_logout_redirect_uri in Keycloak
        params['client_id'] = getattr(settings, 'OIDC_RP_CLIENT_ID', 'django-client-id')
    params['post_logout_redirect_uri'] = request.build_absolute_uri(reverse('home'))

    logout_url = f"{logout_endpoint}?{urlencode(params)}"

    logger.info("logout_view: redirecting to Keycloak logout endpoint=%s", logout_url)
    # Return the raw endpoint for debugging if requested
    if request.GET.get('show') == '1':
        return HttpResponse(logout_url, content_type='text/plain')

    # Redirect browser to Keycloak logout endpoint
    return redirect(logout_url)

def login_view(request):
    """Conditional login view:
    - If invoked as part of an OIDC provider authorization (next contains '/openid/authorize'),
      show the local login form so the provider flow can complete (required for brokered login).
    - Otherwise redirect to OIDC prompt-login to force Keycloak login for application users.
    """
    next_url = request.GET.get('next') or request.POST.get('next')
    # If this is the OIDC provider asking us to authenticate a user, render local login
    if next_url and '/openid/authorize' in next_url:
        data = {}
        if request.method == 'POST':
            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect(next_url or 'dashboard')
            else:
                data['error'] = 'Invalid username and/or password'
        return render(request, 'auth/login.jinja', data)

    # Otherwise, go to Keycloak to log in
    return redirect('oidc_prompt_login')


def oidc_prompt_login(request):
    """Redirect to the OIDC authorization endpoint with prompt=login to force fresh login in Keycloak."""
    import os
    auth_endpoint = getattr(settings, 'OIDC_OP_AUTHORIZATION_ENDPOINT', None) or os.environ.get('OIDC_OP_AUTHORIZATION_ENDPOINT') or 'http://localhost:8080/realms/di4d/protocol/openid-connect/auth'
    redirect_uri = request.build_absolute_uri(reverse('oidc_callback_override_login'))
    params = {
        'response_type': 'code',
        'client_id': getattr(settings, 'OIDC_RP_CLIENT_ID', 'django-client-id'),
        'scope': 'openid profile email',
        'redirect_uri': redirect_uri,
        'prompt': 'login',
    }
    return redirect(auth_endpoint + '?' + urlencode(params))

def student_registration(request):
    return render(request, 'test.jinja')

def news(request):
    search_query = ""
    active_page = 'news'

    # User logged in
    if request.user.is_authenticated:
        all_articles = News.objects.filter().order_by("-lastEditDate")
        total_articles = all_articles.count()
    # User not logged in
    else:
        all_articles = News.objects.filter(isPublic=True).order_by("-lastEditDate")
        total_articles = all_articles.count()
    
    # Check if somebody want to sort by oldest
    if request.POST.get("sort_by") == "oldest":
        all_articles = all_articles.order_by("lastEditDate")

    # Check if somebody searched for something
    if request.method == "POST":
        search_query = request.POST.get("q").strip()
        # Check if search query is not empty
        if search_query:
            all_articles = all_articles.filter(Q(title__icontains=search_query) | Q(lastEditDate__icontains=search_query))
        # Check if there is HTMX request
        if request.headers.get("HX-Request") == "true":
            return render(request, 'components/news_htmx.jinja', {"all_articles": all_articles, "total_articles": total_articles, "search_query": search_query, "active_page": active_page})
    if request.user.is_authenticated:
        return render(request, 'sharepoint/news.jinja', {"all_articles": all_articles, "total_articles": total_articles, "search_query": search_query, "active_page": active_page})
    else:
        return render(request, 'public/news.jinja', {"all_articles": all_articles, "total_articles": total_articles, "search_query": search_query, "active_page": active_page})

@login_required(login_url='oidc_authentication_init')
def dashboard(request):
    active_page = 'dashboard'
    return render(request, 'sharepoint/dashboard.jinja', {'active_page': active_page})

@login_required(login_url='oidc_authentication_init')
def settings(request):
    active_page = 'settings'
    if request.method == 'POST':
        # Check if it is to change password
        if request.POST.get("changepassword"):
            new_password = request.POST.get("newpassword")
            confirm_password = request.POST.get("confirmnewpassword")
            if new_password == confirm_password and new_password != "" and confirm_password != "":
                request.user.set_password(new_password)
                request.user.save()
                # Keep the user logged in after changing password
                update_session_auth_hash(request, request.user)

                return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_password': "Password changed successfully"})
            else:
                return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'error_password': "Passwords do not match and/or are empty"})
        # Check if it is to change profile settings
        if request.POST.get("changeprofile"):
            firstname = request.POST.get("firstname")
            lastname = request.POST.get("lastname")
            email = request.POST.get("email")
            # Update user info
            request.user.first_name = firstname
            request.user.last_name = lastname
            request.user.email = email
            # Check if there was a profile picture uploaded
            if request.FILES.get("profilepicture"):
                # Image will be automatically saved to the correct location because of the ImageField in the User model (pillow)
                request.user.profilePicture = request.FILES["profilepicture"]
            request.user.save()
            return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_profile': "Profile updated successfully"})

    return render(request, 'sharepoint/settings.jinja', {'active_page': active_page})
