# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Configuration health: the collector over tagged system checks, its endpoints, and the toolbox check."""

import sys
from importlib.machinery import ModuleSpec
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from django.core.checks import Info, Warning
from django.core.checks.registry import CheckRegistry

from django_munin import checks as munin_checks
from django_munin.services import health_service

URL = "/api/munin/v2/health/"


def _warning(code: str, **obj) -> Warning:
    return Warning(f"{code} broken", hint="fix it", id=code, obj={"state": "unconfigured", **obj})


@pytest.fixture
def registry():
    """An empty check registry in place of Django's global one."""
    fresh = CheckRegistry()
    with patch.object(health_service, "registry", fresh), patch.object(munin_checks, "registry", fresh):
        yield fresh


def _module(name: str, **attrs) -> ModuleType:
    module = ModuleType(name)
    module.__spec__ = ModuleSpec(name, loader=None)
    module.__dict__.update(attrs)
    return module


@pytest.fixture
def toolbox_status():
    """Stand-in `django_utils.toolbox.status.status` — the same with or without the real client installed."""
    status = Mock()
    fakes = {
        "django_utils.toolbox": _module("django_utils.toolbox"),
        "django_utils.toolbox.status": _module("django_utils.toolbox.status", status=status),
    }
    with patch.dict(sys.modules, fakes):
        yield status


class TestCollect:
    def test_failing_rows_first_by_severity_then_passing_codes(self, registry):
        registry.register(lambda **kw: [_warning("b.low", severity="low")], "entirius_config", "b.low")
        registry.register(lambda **kw: [], "entirius_config", "a.ok")
        registry.register(lambda **kw: [_warning("c.high", severity="high", scope="eu")], "entirius_config", "c.high")
        rows = health_service.collect()
        assert [(r["code"], r["state"]) for r in rows] == [
            ("c.high", "unconfigured"),
            ("b.low", "unconfigured"),
            ("a.ok", "configured"),
        ]
        assert rows[0] == {
            "code": "c.high",
            "module": "c",
            "state": "unconfigured",
            "severity": "high",
            "title": "c.high broken",
            "detail": "fix it",
            "fix_url": "",
            "scope": "eu",
            "probe": False,
        }

    def test_checks_are_asked_to_report_their_state(self, registry):
        seen = {}
        registry.register(lambda **kw: seen.update(kw) or [], "entirius_config", "a.state")
        health_service.collect()
        assert seen[health_service.REPORT_STATE_KWARG] is True

    def test_informational_row_sorts_after_failing_and_before_configured(self, registry):
        info = Info("d.off off", hint="on purpose", id="d.off", obj={"state": "disabled", "severity": "high"})
        registry.register(lambda **kw: [info], "entirius_config", "d.off")
        registry.register(lambda **kw: [], "entirius_config", "a.ok")
        registry.register(lambda **kw: [_warning("b.low", severity="low")], "entirius_config", "b.low")
        rows = health_service.collect()
        assert [(r["code"], r["state"], r["severity"]) for r in rows] == [
            ("b.low", "unconfigured", "low"),
            ("d.off", "disabled", ""),
            ("a.ok", "configured", ""),
        ]
        assert (rows[1]["title"], rows[1]["detail"]) == ("d.off off", "on purpose")

    def test_untagged_checks_are_ignored(self, registry):
        registry.register(lambda **kw: [_warning("x.y")], "models")
        assert health_service.collect() == []

    def test_checks_get_the_database(self, registry):
        seen = {}
        registry.register(lambda **kw: seen.update(kw) or [], "entirius_config", "a.db")
        health_service.collect()
        assert seen["databases"] == ["default"]

    def test_probes_run_only_on_request_and_merge_by_code(self, registry):
        registry.register(lambda **kw: [], "entirius_config", "mail.smtp")
        registry.register(
            lambda **kw: [_warning("mail.smtp", state="auth_failed")], "entirius_probe", "mail.smtp", deploy=True
        )
        assert health_service.collect() == [health_service._passing_row("mail.smtp")]
        [row] = health_service.collect(probe=True)
        assert (row["code"], row["state"], row["probe"]) == ("mail.smtp", "auth_failed", True)

    def test_a_raising_check_is_an_error_row(self, registry):
        def broken(**kw):
            raise RuntimeError("boom")

        registry.register(broken, "entirius_config", "a.broken")
        [row] = health_service.collect()
        assert (row["code"], row["state"]) == ("a.broken", "error")


@pytest.mark.django_db
class TestEndpoints:
    def test_401_no_auth(self, api_client):
        assert api_client.get(URL).status_code == 401

    def test_403_regular_user(self, regular_client):
        assert regular_client.get(URL).status_code == 403

    def test_list_runs_config_checks(self, admin_client, registry):
        registry.register(lambda **kw: [_warning("a.x", severity="high")], "entirius_config", "a.x")
        registry.register(lambda **kw: [_warning("a.p")], "entirius_probe", "a.p", deploy=True)
        data = admin_client.get(URL).data
        assert set(data) == {"checked_at", "checks"}
        assert [r["code"] for r in data["checks"]] == ["a.x"]

    def test_recheck_adds_probes(self, admin_client, registry):
        registry.register(lambda **kw: [_warning("a.p")], "entirius_probe", "a.p", deploy=True)
        response = admin_client.post(f"{URL}check/")
        assert response.status_code == 200
        assert [r["code"] for r in response.data["checks"]] == ["a.p"]

    def test_disabled_toolbox_is_one_passing_row_with_its_state(self, admin_client, registry, toolbox_status):
        toolbox_status.return_value = "disabled"
        registry.register(munin_checks.toolbox_reachable, "entirius_config", munin_checks.TOOLBOX_CODE)
        [row] = admin_client.get(URL).data["checks"]
        assert row == {
            "code": "toolbox.status",
            "module": "toolbox",
            "state": "disabled",
            "severity": "",
            "title": "AI toolbox disabled",
            "detail": "AI_TOOLBOX_ENABLED is False on this instance: AI features are switched off on purpose.",
            "fix_url": munin_checks.TOOLBOX_FIX_URL,
            "scope": "",
            "probe": False,
        }


class TestToolboxCheck:
    def test_registered_only_with_the_client_installed(self, registry):
        with patch.object(munin_checks, "find_spec", return_value=None):
            munin_checks.register()
        assert registry.get_checks() == []
        with patch.object(munin_checks, "find_spec", return_value=object()):
            munin_checks.register()
        [check] = registry.get_checks()
        assert set(check.tags) == {"entirius_config", "toolbox.status"}

    def test_configured_passes(self, toolbox_status):
        toolbox_status.return_value = "configured"
        assert munin_checks.toolbox_reachable() == []

    def test_disabled_is_silent_for_the_django_runner(self, toolbox_status):
        toolbox_status.return_value = "disabled"
        assert munin_checks.toolbox_reachable() == []
        assert munin_checks.toolbox_reachable(app_configs=None, databases=["default"]) == []

    def test_disabled_is_an_info_row_when_state_is_reported(self, toolbox_status):
        toolbox_status.return_value = "disabled"
        [message] = munin_checks.toolbox_reachable(report_state=True)
        assert isinstance(message, Info)
        assert (message.id, message.msg) == ("toolbox.status", "AI toolbox disabled")
        assert "AI_TOOLBOX_ENABLED is False" in message.hint
        assert message.obj == {"state": "disabled", "severity": "", "fix_url": munin_checks.TOOLBOX_FIX_URL}

    def test_configured_passes_when_state_is_reported(self, toolbox_status):
        toolbox_status.return_value = "configured"
        assert munin_checks.toolbox_reachable(report_state=True) == []

    @pytest.mark.parametrize("report_state", [False, True])
    @pytest.mark.parametrize(("state", "severity"), [("unconfigured", "medium"), ("unreachable", "high")])
    def test_failing_states(self, toolbox_status, state, severity, report_state):
        toolbox_status.return_value = state
        [message] = munin_checks.toolbox_reachable(report_state=report_state)
        assert isinstance(message, Warning)
        assert message.id == "toolbox.status"
        assert (message.obj["state"], message.obj["severity"]) == (state, severity)
        assert message.obj["fix_url"].startswith("https://")
        assert str(message).startswith("settings: (toolbox.status) ")  # CLI label, not the dict
