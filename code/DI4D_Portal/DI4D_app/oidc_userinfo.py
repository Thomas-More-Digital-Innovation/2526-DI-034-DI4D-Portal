from .models import User

def oidc_userinfo(user):
    return {
        'sub': str(user.id),
        'name': user.firstname + ' ' + user.lastname,
        'email': user.email,
        'preferred_username': user.username,
        # Add more claims as needed
    }
