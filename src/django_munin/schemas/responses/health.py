# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic response schemas for configuration health."""

from datetime import datetime

from pydantic import BaseModel, Field


class ConfigCheckRow(BaseModel):
    code: str = Field(description="Check code, `<module>.<check>`", examples=["email.smtp"])
    module: str = Field(description="Munin module key the check belongs to", examples=["email"])
    state: str = Field(
        description="configured, unconfigured, unreachable, auth_failed, disabled (switched off on purpose, not "
        "failing), or error (the check itself raised)",
        examples=["unconfigured"],
    )
    severity: str = Field(description="high, medium or low; empty when configured or disabled", examples=["high"])
    title: str = Field(description="English one-liner; empty when configured", examples=["SMTP not configured"])
    detail: str = Field(description="What is wrong and what to set", examples=["Add a complete entry."])
    fix_url: str = Field(description="Where it is fixed: absolute docs URL or a CMS path", examples=["https://…"])
    scope: str = Field(description="Channel idx for channel-bound checks, else empty", examples=["default-europe"])
    probe: bool = Field(
        description="Found by a live probe (only in `health/check/`); a plain `health/` read never repeats it",
        examples=[False],
    )


class ConfigHealthResponse(BaseModel):
    checked_at: datetime = Field(description="When the checks ran")
    checks: list[ConfigCheckRow] = Field(
        description="Failing rows first (by severity), then disabled rows, then passing check codes"
    )
