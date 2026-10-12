---
title: Munin
description: Module discovery and runtime configuration — auto-detects installed Volkanos modules and serves them via REST API.
sidebar:
  label: Overview
  collapsed: true
---

django-munin is the platform's module registry. It scans `INSTALLED_APPS` for Volkanos modules (AppConfigs with `is_volkanos = True`), introspects their structure — models, API, admin API, channels, translations, fixtures — and persists the result to a `Module` table served over REST. Frontends read this instead of hardcoding module lists: the CMS sidebar shows exactly the panels the backend actually runs.

## What It Does

- Discovers Volkanos apps and introspects capabilities (`has_models`, `has_api`, `has_admin_api`, `has_channels`, `has_translations`, ...)
- Upserts `Module` rows — auto-detected fields are overwritten on every scan, admin-controlled fields (`enabled_in_cms`, `display_order`, `config`) are preserved
- Deactivates modules removed from `INSTALLED_APPS` (`is_active=False`, config kept for re-addition)
- Runs automatically after every `migrate` via a `post_migrate` receiver (since 1.1.0); manual re-scan via `manage.py discover_modules`
- Serves runtime key-value configuration (`ConfigEntry`) for admins

## API Surface

Prefix `/api/munin/v2/`:

| Method | Endpoint | Access |
|---|---|---|
| GET | `/` | AllowAny — public fields; admins (JWT + staff) additionally get `enabled_in_cms`, `display_order`, `app_label` |
| GET | `/{key}/` | AllowAny — single module by key |
| GET/POST | `/admin/entries/` | IsAdminUser — config entries (paginated) |
| PATCH/DELETE | `/admin/entries/{key}/` | IsAdminUser |

Responses are cached (`MUNIN_CACHE_TTL`, default 300s); cache invalidates via post_save/post_delete signals on `Module` and `ConfigEntry`.

## Configuration Health

| Method | Path | Auth |
|---|---|---|
| GET | `/health/` | IsAdminUser — config checks, computed on every read (never cached by munin) |
| POST | `/health/check/` | IsAdminUser, and the write level of `munin.config` where the access module is installed — config checks plus live probes ("Check again") |

Munin aggregates every Django system check tagged `entirius_config`; a check's second tag is its code
(`email.smtp`). Each row carries `code`, `module`, `state`, `severity`, `title`, `detail`, `fix_url`, `scope`;
failing rows come first, then one `configured` row per passing code. `state` is `configured`, `unconfigured`,
`unreachable`, `auth_failed`, `disabled` or `error`. `disabled` is a passing row with its state visible: something
switched off on purpose, `severity` empty, listed after the failing rows and before the `configured` ones. Probes (tag `entirius_probe`, registered
`deploy=True`) run only on `POST /health/check/`. The same verdicts from the CLI:

```bash
python manage.py check --database default --tag entirius_config
```

Munin registers `toolbox.status` itself when `django_utils.toolbox` is installed — `django_utils.toolbox.status()`
as a check (probe cached 60 s). `unconfigured` and `unreachable` are warnings. With `AI_TOOLBOX_ENABLED = False`
the toolbox is `disabled`: the check passes, `health/` shows the row with `state: disabled`, and the CLI prints
nothing for it. Munin calls every check with `report_state=True`; a check that accepts the keyword may answer a
`checks.Info` for such a state, while Django's own runner (`check`, `runserver`, `migrate`) never passes it.

The public registry `GET /api/munin/v2/` carries the same state as `platform.toolbox.state` (`configured`,
`unconfigured`, `unreachable` or `disabled`; `platform.toolbox` is `null` when the toolbox client is not
installed), so a test suite can read it without admin credentials. The contract for adding a check lives in the portal guide *Configuration*.

## Consumers

- **cms-blueprint** — panel enablement (`useMuninStore`, `GET /api/munin/v2/`); `enabled_in_cms` toggled in Django admin drives the CMS sidebar
- Other modules — runtime config via `config_service.get_config_value()` (consume with `try/except ImportError`)

## Dependencies

- `django-utils` — `BaseModel` timestamps; optionally `django_utils.toolbox` for the `toolbox.status` check
