from jinja2 import Environment
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

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
    })
    return env
