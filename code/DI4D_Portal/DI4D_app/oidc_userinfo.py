import logging
from .models import User

logger = logging.getLogger(__name__)

def oidc_userinfo(claims, user):
    """
    Populate the OIDC userinfo claims.

    Called by oidc_provider with signature (claims, user).
    Return a dict with additional/overridden claims.
    """
    try:
        name = "".join([p for p in (user.firstname or '', ' ', user.lastname or '')]).strip()
    except Exception:
        name = ''

    info = {
        'sub': str(getattr(user, 'id', '')),
        'name': name,
        'given_name': getattr(user, 'firstname', '') or '',
        'family_name': getattr(user, 'lastname', '') or '',
        'preferred_username': getattr(user, 'username', '') or getattr(user, 'email', '') or str(getattr(user, 'id', '')),
        'email': getattr(user, 'email', '') or '',
        'email_verified': bool(getattr(user, 'email', '')),
    }

    logger.info('OIDC userinfo requested for user=%s, returning keys=%s', getattr(user, 'id', None), list(info.keys()))
    return info
