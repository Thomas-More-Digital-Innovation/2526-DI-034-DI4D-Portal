from pathlib import Path
from uuid import uuid4

from django.core.files.storage import Storage, storages


class CKEditorNewsPictureStorage(Storage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_storage = storages["default"]

    def save(self, name, content, max_length=None):
        extension = Path(name).suffix.lower()
        unique_name = f"news_pictures/{uuid4().hex}{extension}"
        return self.base_storage.save(unique_name, content, max_length=max_length)

    def open(self, name, mode="rb"):
        return self.base_storage.open(name, mode)

    def exists(self, name):
        return self.base_storage.exists(name)

    def url(self, name):
        url = self.base_storage.url(name)
        # CKEditor preview needs a URL that is valid from nested admin routes.
        # Normalize plain relative paths to root-relative URLs.
        if isinstance(url, str) and url and not url.startswith(("http://", "https://", "//", "/")):
            return f"/{url.lstrip('/')}"
        return url
