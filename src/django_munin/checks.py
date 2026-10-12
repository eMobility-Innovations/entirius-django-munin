# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Munin's own configuration check: the AI toolbox, registered only when its client is installed."""

from importlib.util import find_spec

from django.core import checks
from django.core.checks.registry import registry

TOOLBOX_CODE = "toolbox.status"
TOOLBOX_FIX_URL = "https://github.com/entirius/entirius-django-utils/blob/master/docs/toolbox-client.md#settings"
_TOOLBOX_TEXT = {
    "unconfigured": (
        "AI toolbox not configured",
        "Set AI_TOOLBOX_BASE_URL, AI_TOOLBOX_API_KEY and AI_TOOLBOX_CHANNEL.",
    ),
    "unreachable": ("AI toolbox unreachable", "The toolbox did not answer GET models/ for AI_TOOLBOX_CHANNEL."),
}
_DISABLED_HINT = "AI_TOOLBOX_ENABLED is False on this instance: AI features are switched off on purpose."


class _Subject(dict):
    """Row metadata munin reads as a dict; `manage.py check` prints `str(obj)` as the label, so name the subject."""

    def __str__(self) -> str:
        return self.get("scope") or "settings"


def toolbox_reachable(app_configs=None, report_state: bool = False, **kwargs) -> list[checks.CheckMessage]:
    """`django_utils.toolbox.status()` as a check — cached 60 s probe, never raises (unchanged from 2.1.0).

    `disabled` passes; with `report_state` (munin's collector only, never Django's own runner) it is one Info row.
    """
    from django_utils.toolbox.status import status

    state = str(status())
    if state == "disabled" and report_state:
        return [_disabled_info()]
    if state not in _TOOLBOX_TEXT:
        return []
    title, detail = _TOOLBOX_TEXT[state]
    severity = "high" if state == "unreachable" else "medium"
    return [
        checks.Warning(
            title, hint=detail, id=TOOLBOX_CODE, obj=_Subject(state=state, severity=severity, fix_url=TOOLBOX_FIX_URL)
        )
    ]


def _disabled_info() -> checks.Info:
    subject = _Subject(state="disabled", severity="", fix_url=TOOLBOX_FIX_URL)
    return checks.Info("AI toolbox disabled", hint=_DISABLED_HINT, id=TOOLBOX_CODE, obj=subject)


def register() -> None:
    if find_spec("django_utils.toolbox") is not None:
        registry.register(toolbox_reachable, "entirius_config", TOOLBOX_CODE)
