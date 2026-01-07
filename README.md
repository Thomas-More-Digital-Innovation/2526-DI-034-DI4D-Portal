# DI4D Portal
## Technology
- Django [Django Docs](https://docs.djangoproject.com/)
- Tailwind CSS [Tailwind CSS Docs](https://v2.tailwindcss.com/docs)
- Jinja2 [Jinja2 Docs](https://www.devdoc.net/python/jinja-2.10.1-doc/)
- Alpine.js [Alpine JS Docs](https://alpinejs.dev/start-here)
- HTMX [HTMX Docs](https://htmx.org/docs/)

## Structure of the Django DI4D Portal
- DI4D_Portal : This is the name/folder of our hole project.
- DI4D_app : This is the app we are going to use. We only use one app for the hole application.

## Important commando's Django
-  Create new app : python manage.py startapp <app_name>
- Make migrations : python manage.py makemigrations
- Run migrations : python manage.py migrate
- Create a super user : python manage.py createsuperuser
- Run server : python manage.py runserver

## Setup development environment (Windows)
- Create venv: python -m venv .\code\\.venv
- Activate venv: .\code\\.venv\Scripts\Activate.ps1
- Upgrade pip: python -m pip install -U pip
- Install deps from pyproject.toml: pip install -e .\code\.
- Install tailwind binary: python .\code\DI4D_Portal\manage.py tailwind install
- Run dev environment: Ctrl + Shift + p, Task: run task, choose dev.
