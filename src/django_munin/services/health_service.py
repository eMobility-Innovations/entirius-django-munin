# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Configuration health: every Django system check tagged ``entirius_config`` (plus ``entirius_probe`` on request).

A check's second tag is its code (``email.smtp``); a check that returns nothing is one ``configured`` row, so the
CMS can show what passed. Never cached — checks own their caches, and a fixed config must clear on the next read.

Every check is called with ``report_state=True``: a check may then answer a message below ``WARNING`` for a state
that passes but is worth showing (the toolbox switched off on purpose). That is an informational row — the state
of the message, empty severity — and it stands for the code, so no ``configured`` row is added.
"""

import logging

from django.core import checks
from django.core.checks import CheckMessage
from django.core.checks.registry import registry

logger = logging.getLogger(__name__)

CONFIG_TAG = "entirius_config"
PROBE_TAG = "entirius_probe"
REPORT_STATE_KWARG = "report_state"
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def collect(probe: bool = False) -> list[dict]:
    """Failing rows first (by severity), then informational rows, then one ``configured`` row per silent code."""
    tags = {CONFIG_TAG, PROBE_TAG} if probe else {CONFIG_TAG}
    reported: dict[str, list[dict]] = {}
    for check in registry.get_checks(include_deployment_checks=probe):
        if tags.isdisjoint(check.tags):
            continue
        code = _code(check)
        rows = _run(check, code)
        if rows is not None:
            reported.setdefault(code, []).extend(rows)
    rows = sorted((r for rs in reported.values() for r in rs), key=lambda r: _SEVERITY_ORDER.get(r["severity"], 3))
    return rows + [_passing_row(code) for code, rs in sorted(reported.items()) if not rs]


def _code(check) -> str:
    extra = [t for t in check.tags if t not in (CONFIG_TAG, PROBE_TAG)]
    return extra[0] if extra else f"{check.__module__}.{check.__name__}"


def _run(check, code: str) -> list[dict] | None:
    probe = PROBE_TAG in check.tags
    try:
        messages = list(check(app_configs=None, databases=["default"], **{REPORT_STATE_KWARG: True}))
        visible = [message for message in messages if not message.is_silenced()]
        if messages and not visible:
            return None  # Silenced is omitted, not evidence that this check passed.
        return [{**_message_row(code, m), "probe": probe} for m in visible]
    except Exception:  # noqa: BLE001 — one broken check must not take the whole panel down
        logger.exception("Configuration check %s raised", code)
        return [_row(code, state="error", severity="medium", title="Configuration check failed to run", probe=probe)]


def _message_row(code: str, message: CheckMessage) -> dict:
    """A failing row, or an informational one (empty severity) for a message below ``WARNING``."""
    extra = message.obj if isinstance(message.obj, dict) else {}
    return _row(
        message.id or code,
        state=extra.get("state", "unconfigured"),
        severity=extra.get("severity", "medium") if message.level >= checks.WARNING else "",
        title=message.msg,
        detail=message.hint or "",
        fix_url=extra.get("fix_url", ""),
        scope=extra.get("scope", ""),
    )


def _passing_row(code: str) -> dict:
    return _row(code, state="configured", severity="")


def _row(code: str, **fields) -> dict:
    return {
        "code": code,
        "module": code.split(".")[0],
        "title": "",
        "detail": "",
        "fix_url": "",
        "scope": "",
        "probe": False,
        **fields,
    }
