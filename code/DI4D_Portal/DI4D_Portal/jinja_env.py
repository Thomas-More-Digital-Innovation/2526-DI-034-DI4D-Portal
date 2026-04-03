from jinja2 import Environment
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from django.conf import settings


try:
    from livereload.templatetags.livereload_tags import livereload_script
except ImportError:
    livereload_script = lambda: ''

def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
        'livereload_script': livereload_script,
        'TURNSTILE_SITE_KEY': settings.TURNSTILE_SITE_KEY,
    })
    return env
