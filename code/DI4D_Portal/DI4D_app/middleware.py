import logging

logger = logging.getLogger(__name__)

class OIDCLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/openid/') and request.method in ('GET', 'POST'):
            auth = request.META.get('HTTP_AUTHORIZATION')
            logger.info(f"OIDC request: method={request.method} path={request.path} GET={dict(request.GET)} POST={dict(request.POST)} AUTH={auth}")
        response = self.get_response(request)
        # Log userinfo response body for debugging
        try:
            if request.path.startswith('/openid/userinfo'):
                content = response.content.decode('utf-8') if hasattr(response, 'content') else str(response)
                logger.info(f"OIDC userinfo response: {content}")
        except Exception:
            logger.exception('Failed to log OIDC userinfo response')
        return response
