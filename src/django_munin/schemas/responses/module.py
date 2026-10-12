# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for Munin module data."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ToolboxInfo(BaseModel):
    state: str = Field(description="configured, unconfigured, unreachable or disabled", examples=["configured"])


class PlatformInfo(BaseModel):
    version: str = Field(description="Platform version", examples=["2.0.0"])
    toolbox_status: str | None = Field(
        None,
        description="Deprecated — read `toolbox.status` from `GET /api/munin/v2/health/`; removed in 3.0.0. "
        "AI toolbox availability: configured, unconfigured, unreachable or disabled; null when the toolbox client is not "
        "installed",
        examples=["configured"],
        json_schema_extra={"deprecated": True},
    )
    toolbox: ToolboxInfo | None = Field(
        None, description="AI toolbox availability; null when the toolbox client is not installed"
    )


class ModulePublicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str = Field(description="Human-readable module name", examples=["Product Information Management"])
    version: str = Field(description="Module version", examples=["1.14.0"])
    has_models: bool = Field(description="Module has Django models", examples=[True])
    has_api: bool = Field(description="Module has API endpoints", examples=[True])
    has_admin_api: bool = Field(description="Module has admin API (v2)", examples=[True])
    has_admin: bool = Field(description="Module has Django admin", examples=[True])
    has_management_commands: bool = Field(description="Module has management commands", examples=[True])
    has_urls: bool = Field(description="Module has URL patterns", examples=[True])
    has_channels: bool = Field(description="Module has channel support", examples=[True])
    has_translations: bool = Field(description="Module has translation support", examples=[True])
    has_fixtures: bool = Field(description="Module has fixture files", examples=[False])
    config: dict = Field(default_factory=dict, description="Module-specific configuration", examples=[{}])


class ModuleAdminResponse(ModulePublicResponse):
    app_label: str = Field(description="Django app label", examples=["django_pim"])
    is_active: bool = Field(description="Module is active (in INSTALLED_APPS)", examples=[True])
    enabled_in_cms: bool = Field(description="Module is enabled in CMS", examples=[True])
    display_order: int = Field(description="Display order in CMS", examples=[0])
    created_at: datetime | None = Field(None, description="Creation timestamp", examples=["2024-01-01T00:00:00Z"])
    modified_at: datetime | None = Field(None, description="Last update timestamp", examples=["2024-01-01T00:00:00Z"])


class MuninListResponse(BaseModel):
    platform: PlatformInfo = Field(description="Platform information")
    modules: dict[str, ModulePublicResponse] = Field(description="Installed modules keyed by module key")


class MuninAdminListResponse(BaseModel):
    platform: PlatformInfo = Field(description="Platform information")
    modules: dict[str, ModuleAdminResponse] = Field(description="Installed modules keyed by module key")
