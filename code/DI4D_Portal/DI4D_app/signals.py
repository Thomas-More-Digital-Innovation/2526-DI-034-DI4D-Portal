import logging
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

logger = logging.getLogger(__name__)

@receiver(user_logged_in)
def log_user_logged_in(sender, request, user, **kwargs):
    logger.info(f"User logged in via Django auth: id={user.id} username={user.username} ip={request.META.get('REMOTE_ADDR')}")

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get('username') if credentials else None
    logger.warning(f"User login failed: username={username} ip={request.META.get('REMOTE_ADDR') if request else 'unknown'}")
