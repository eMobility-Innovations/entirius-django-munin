# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The module owns its access rules: areas on its AppConfig, an `access_area` on every admin view."""

import pytest

pytest.importorskip("django_access")

from django.apps import apps  # noqa: E402
from django_access.catalogue.areas import DEFAULT_AREAS, Area  # noqa: E402
from django_access.catalogue.scopes import DEFAULT_SCOPES, TokenScope  # noqa: E402
from django_access.services import route_map  # noqa: E402
from django_access.testing import assert_routes_covered  # noqa: E402

LABEL = "django_munin"


def test_admin_routes_are_covered_by_own_declarations():
    assert_routes_covered(LABEL, urlconf="django_munin.urls", require_own=True)


def test_declarations_match_the_access_defaults():
    """Same areas and scopes as the access defaults; delete with those defaults in a later access release."""
    config = apps.get_app_config(LABEL)
    areas = [Area(**{**item, "module": LABEL}) for item in config.access_areas]
    scopes = [TokenScope(**{**item, "module": LABEL}) for item in getattr(config, "access_token_scopes", [])]
    assert areas == [item for item in DEFAULT_AREAS if item.module == LABEL]
    assert scopes == [item for item in DEFAULT_SCOPES if item.module == LABEL]


def _required(suffix: str, method: str) -> str | None:
    [info] = [
        route_map.classify(route, view) for route, view in route_map.walk("django_munin.urls") if route.endswith(suffix)
    ]
    return route_map.required_permission(info, method)


def test_recheck_with_live_probes_needs_the_write_level():
    assert _required("health/check/", "POST") == "munin.config:write"


def test_cached_health_stays_readable():
    assert _required("health/", "GET") == "munin.config:read"
