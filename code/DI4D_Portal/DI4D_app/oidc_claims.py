from oidc_provider.lib.claims import ScopeClaims
from .models import User

class OIDCExtraScopeClaims(ScopeClaims):
    def scope_profile(self):
        return {
            'name': self.user.firstname + ' ' + self.user.lastname,
            'email': self.user.email,
            'preferred_username': self.user.username,
        }

    def scope_email(self):
        return {
            'email': self.user.email,
        }

    def scope_custom(self):
        # Add any custom claims here
        return {}
