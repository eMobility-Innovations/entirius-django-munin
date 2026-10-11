# AGENTS.md

`entirius-django-munin` (Django app `django_munin`) — module discovery and runtime configuration for Entirius.
Auto-discovers installed Entirius modules via the `is_volkanos = True` flag on AppConfig, introspects their structure (models, API, channels, translations…), persists to DB,
and serves via REST API. Frontends read this instead of hardcoding module lists.

## Commands

| Command | Meaning |
|---|---|
| `make install` | sync dependencies (uv, incl. extras) |
| `make check` | lint + format-check (ruff) |
| `make fix` | auto-fix lint + format |
| `make test` | test suite (pytest + pytest-django) |

## Conventions

- English only: code, docs, commits, branches, PRs.
- MPL-2.0: every non-trivial source file carries the license header (pre-commit inserts it).
- Toolchain: uv + ruff + hatchling + pytest; all config in `pyproject.toml`; `uv.lock` committed.
- Git flow: `master` (production) + `develop` (integration); changes land via PR; semver tag on `master`.
- Never rename the package / Django app_label / DB table prefix `django_munin` — it is a schema contract.
- Migrations are part of the public contract — never edit an already released migration.
- Access: areas live on the AppConfig (`access_areas`, `access_route_rules`), every admin view carries
  `access_area`; a new admin route without one fails `tests/test_access_ownership.py`.
- Default: do not commit — git is the user's call.
- No AI attribution in commits or PR descriptions.

## Architecture

- `models/` — `Module` (auto-detected capabilities + admin settings), `ConfigEntry` (runtime
  key-value config, dotted keys, JSON values).
- `introspection.py` — pure detection functions (`has_models`, `has_api`, …).
- `services/` — `discovery_service.scan_modules()` (introspect + upsert), `config_service`
  (aggregation, caching, ConfigEntry CRUD).
- `schemas/` — pydantic request/response schemas.
- `api/` — `MuninViewSet` (AllowAny; admin JWT gets extra fields), `ConfigEntryViewSet`
  (JWT + IsAdminUser), pagination, permissions; root prefix `api/munin/v2/`.
  `ConfigHealthViewSet` (IsAdminUser) serves `health/` and `health/check/` — listed before `<str:key>/`,
  which would take "health" for a module key. Access area `munin.config`: `health/` is a read, the
  `health/check/` POST a write (it runs live probes, for example an SMTP login).
- `services/health_service.py` — runs the system checks tagged `entirius_config` (+ `entirius_probe` on
  request) with `databases=["default"]` and `report_state=True` (a message below `WARNING` is a passing row with
  its state shown, e.g. the toolbox `disabled`); never cached. `checks.py` registers `toolbox.status` only when
  `find_spec("django_utils.toolbox")` finds the client; munin never hard-imports the toolbox.
- `management/commands/discover_modules.py` — manual re-scan entry point.

Layer rule: `API → Services → Models → DB`. No ORM in views.

| Topic | Where |
|---|---|
| API surface, configuration health, consumers | `docs/index.md` |
| ERD config for the docs ERD generator | `docs/erd-config.yaml` |

## Settings

| Setting | Default | Description |
|---|---|---|
| `MUNIN_CACHE_TTL` | `300` | Cache lifetime of the registry responses, in seconds |

## Gotchas

- Discovery runs automatically after every `migrate` via a `post_migrate` receiver in `apps.py`.
  Do NOT call `scan_modules()` from `AppConfig.ready()` — ready() fires before tables exist.
- Auto-detected fields (`has_*`, label, version) are overwritten on every scan; admin-controlled
  fields (`enabled_in_cms`, `display_order`, `config`) are set on first create and preserved.
- Modules removed from INSTALLED_APPS get `is_active=False`, never deleted — config survives re-adding.
- Consumers of `config_service.get_config_value()` should guard with `try/except ImportError`.
- Cache invalidation is version-bumping via post_save/post_delete signals; all signals carry `dispatch_uid`.
