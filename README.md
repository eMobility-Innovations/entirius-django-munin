# entirius-django-munin

A Django module registry for Entirius, the open-source modular ecommerce platform: it discovers the installed modules and serves them over a REST API.
It also stores runtime key-value configuration and reports configuration health, so frontends read what the backend
runs instead of hardcoding module lists.

[![PyPI](https://img.shields.io/pypi/v/entirius-django-munin.svg)](https://pypi.org/project/entirius-django-munin/)
[![Python](https://img.shields.io/pypi/pyversions/entirius-django-munin.svg)](https://pypi.org/project/entirius-django-munin/)
[![License: MPL-2.0](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](https://github.com/entirius/entirius-django-munin/blob/develop/LICENSE)

## What it does

- Discovers the installed Entirius modules (apps whose `AppConfig` sets `is_volkanos = True`) and records their
  capabilities: models, API, admin API, channels, translations, fixtures.
- Re-scans after every `migrate`; `discover_modules` runs the scan by hand.
- Keeps admin-controlled fields (`enabled_in_cms`, `display_order`, `config`) across scans and deactivates modules
  that left `INSTALLED_APPS` instead of deleting them.
- Serves the registry publicly under `api/munin/v2/`, with extra fields for staff.
- Stores runtime configuration entries (dotted keys, JSON values) with an admin API and a read helper for other modules.
- Aggregates the Django system checks tagged `entirius_config` into a configuration health endpoint.

## Installation

```shell
uv add entirius-django-munin
pip install entirius-django-munin
```

```python
INSTALLED_APPS = [
    ...
    "django_utils",
    "django_munin",
]

# urls.py
urlpatterns = [
    path("", include("django_munin.urls")),
]
```

```shell
python manage.py migrate            # creates the tables and runs discovery
python manage.py discover_modules   # manual re-scan
```

Optional setting: `MUNIN_CACHE_TTL`; reference with the default in
https://github.com/entirius/entirius-django-munin/blob/develop/AGENTS.md (section Settings).

## Quick start

```python
from django_munin.services.config_service import get_config_value

page_size = get_config_value("catalog.page_size", default=24)
```

## Requirements

- Python 3.11 or newer, Django 5.0 or newer.
- Django REST Framework, `djangorestframework-simplejwt`, `pydantic`, `drf-spectacular`.
- Entirius packages pulled in: `entirius-django-utils`.

## Documentation

- Module docs: https://github.com/entirius/entirius-django-munin/tree/develop/docs
- Entirius documentation: https://docs.entirius.com/
- Changelog: https://github.com/entirius/entirius-django-munin/blob/develop/CHANGELOG.md

## Part of Entirius

This module runs inside the Entirius backend service (Volkanos); the admin CMS reads its registry to decide which panels to show.

- Backend service: https://github.com/entirius/entirius-service-volkanos
- Docker harness: https://github.com/entirius/entirius-zeno
- Sibling modules: https://github.com/entirius/entirius-django-utils, https://github.com/entirius/entirius-django-access

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django)
```

Development and agent instructions: https://github.com/entirius/entirius-django-munin/blob/develop/AGENTS.md

## License

Mozilla Public License 2.0 (MPL-2.0) — see https://github.com/entirius/entirius-django-munin/blob/develop/LICENSE.
