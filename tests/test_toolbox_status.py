# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Tests for `platform.toolbox` and the deprecated `platform.toolbox_status` on the module list."""

import sys
from importlib.machinery import ModuleSpec
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from tests.factories import ModuleFactory

PUBLIC_MODULE_FIELDS = {
    "label",
    "version",
    "has_models",
    "has_api",
    "has_admin_api",
    "has_admin",
    "has_management_commands",
    "has_urls",
    "has_channels",
    "has_translations",
    "has_fixtures",
    "config",
}
ADMIN_MODULE_FIELDS = PUBLIC_MODULE_FIELDS | {
    "app_label",
    "is_active",
    "enabled_in_cms",
    "display_order",
    "created_at",
    "modified_at",
}


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


@pytest.mark.django_db
class TestToolboxStatus:
    def test_toolbox_status_absent_client_is_null(self, api_client):
        with patch("django_munin.api.views.find_spec", return_value=None):
            response = api_client.get("/api/munin/v2/")
        assert response.status_code == 200
        assert response.data["platform"]["toolbox_status"] is None
        assert response.data["platform"]["toolbox"] is None

    @pytest.mark.parametrize("state", ["configured", "unconfigured", "unreachable", "disabled"])
    def test_public_registry_carries_the_toolbox_state(self, api_client, toolbox_status, state):
        toolbox_status.return_value = state
        response = api_client.get("/api/munin/v2/")
        assert response.status_code == 200
        assert response.data["platform"]["toolbox"] == {"state": state}
        assert response.data["platform"]["toolbox_status"] == state

    def test_toolbox_status_unconfigured(self, api_client, toolbox_status):
        toolbox_status.return_value = "unconfigured"
        response = api_client.get("/api/munin/v2/")
        assert response.data["platform"]["toolbox_status"] == "unconfigured"

    def test_toolbox_status_configured(self, admin_client, toolbox_status):
        toolbox_status.return_value = "configured"
        response = admin_client.get("/api/munin/v2/")
        assert response.data["platform"]["toolbox_status"] == "configured"

    def test_pre_existing_fields_unchanged(self, api_client, admin_user, toolbox_status):
        toolbox_status.return_value = "configured"
        ModuleFactory(key="pim")
        public = api_client.get("/api/munin/v2/").data
        assert list(public) == ["platform", "modules"]
        assert public["platform"] == {
            "version": "2.0.0",
            "toolbox_status": "configured",
            "toolbox": {"state": "configured"},
        }
        assert set(public["modules"]["pim"]) == PUBLIC_MODULE_FIELDS
        api_client.force_authenticate(user=admin_user)
        admin = api_client.get("/api/munin/v2/").data
        assert list(admin["platform"]) == ["version", "toolbox_status", "toolbox"]
        assert set(admin["modules"]["pim"]) == ADMIN_MODULE_FIELDS
