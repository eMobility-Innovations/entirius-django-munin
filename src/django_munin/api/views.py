# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""API views for Munin module discovery and config entries."""

from importlib.util import find_spec

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.utils import timezone
from django_utils.api.v2_errors import raise_pydantic_as_drf
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from pydantic import ValidationError
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_munin.api.pagination import AdminPageNumberPagination
from django_munin.api.permissions import IsAdminUser
from django_munin.schemas.requests.config_entry import ConfigEntryCreateRequest, ConfigEntryUpdateRequest
from django_munin.schemas.responses.config_entry import ConfigEntryListResponse, ConfigEntryResponse
from django_munin.schemas.responses.health import ConfigHealthResponse
from django_munin.schemas.responses.module import ModulePublicResponse, MuninListResponse
from django_munin.services import config_service, health_service

_ERROR_RESPONSES = {
    400: {"description": "Validation error"},
    401: {"description": "Authentication required"},
    403: {"description": "Permission denied"},
    404: {"description": "Not found"},
}


def _is_admin_request(request: Request) -> bool:
    return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


def _toolbox_status() -> str | None:
    """Toolbox state for the public registry: `platform.toolbox.state`, readable without admin credentials.

    Also sent as `platform.toolbox_status`, deprecated since the config-health release (`toolbox.status` in
    `GET health/` replaces it; removed in 3.0.0) — kept so a CMS older than the health panel keeps its toolbox
    banner after a munin upgrade.
    """
    if find_spec("django_utils.toolbox") is None:
        return None
    from django_utils.toolbox.status import status

    return str(status())


@extend_schema_view(list=extend_schema(tags=["Module Discovery"]), retrieve=extend_schema(tags=["Module Discovery"]))
class MuninViewSet(viewsets.ViewSet):
    """Public module discovery — returns deeper data for admin users."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        summary="List installed modules",
        description="Returns all active Volkanos modules. Admin users see additional fields (enabled_in_cms, display_order, timestamps).",
        responses={200: MuninListResponse},
    )
    def list(self, request: Request, **kwargs) -> Response:
        is_admin = _is_admin_request(request)
        data = config_service.get_module_list(is_admin=is_admin)
        state = _toolbox_status()
        platform = {**data["platform"], "toolbox_status": state, "toolbox": {"state": state} if state else None}
        return Response({**data, "platform": platform})

    @extend_schema(
        summary="Retrieve module by key",
        description="Returns a single module's capabilities. Admin users see additional fields.",
        parameters=[
            OpenApiParameter(
                name="key", location=OpenApiParameter.PATH, type=str, description="Module key (e.g. 'pim')"
            )
        ],
        responses={200: ModulePublicResponse, **_ERROR_RESPONSES},
    )
    def retrieve(self, request: Request, key: str, **kwargs) -> Response:
        is_admin = _is_admin_request(request)
        try:
            data = config_service.get_module_detail(key=key, is_admin=is_admin)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)


@extend_schema_view(
    list=extend_schema(tags=["Munin Config"]),
    create=extend_schema(tags=["Munin Config"]),
    partial_update=extend_schema(tags=["Munin Config"]),
    destroy=extend_schema(tags=["Munin Config"]),
)
class ConfigEntryViewSet(viewsets.ViewSet):
    """Admin CRUD for runtime config entries."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "munin.config"

    @extend_schema(
        summary="List config entries",
        description="Returns a paginated list of all config entries.",
        parameters=[
            OpenApiParameter(name="page", location=OpenApiParameter.QUERY, type=int, description="Page number"),
            OpenApiParameter(
                name="page_size", location=OpenApiParameter.QUERY, type=int, description="Items per page (max 100)"
            ),
        ],
        responses={200: ConfigEntryListResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        qs = config_service.list_config_entries()
        paginator = AdminPageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        results = [ConfigEntryResponse.model_validate(e) for e in page]
        response = ConfigEntryListResponse(
            count=paginator.page.paginator.count,
            next=paginator.get_next_link(),
            previous=paginator.get_previous_link(),
            results=results,
        )
        return Response(response.model_dump(mode="json"))

    @extend_schema(
        summary="Create config entry",
        description="Creates a new runtime config entry.",
        responses={201: ConfigEntryResponse, **_ERROR_RESPONSES},
    )
    def create(self, request: Request, **kwargs) -> Response:
        try:
            data = ConfigEntryCreateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        try:
            entry = config_service.create_config_entry(
                key=data.key, value=data.value, is_public=data.is_public, description=data.description
            )
        except IntegrityError:
            return Response(
                {"detail": f"Entry with key '{data.key}' already exists."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            ConfigEntryResponse.model_validate(entry).model_dump(mode="json"), status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Update config entry",
        description="Partially updates a config entry by key.",
        parameters=[
            OpenApiParameter(name="key", location=OpenApiParameter.PATH, type=str, description="Config entry key")
        ],
        responses={200: ConfigEntryResponse, **_ERROR_RESPONSES},
    )
    def partial_update(self, request: Request, key: str, **kwargs) -> Response:
        try:
            data = ConfigEntryUpdateRequest(**request.data)
        except ValidationError as exc:
            raise_pydantic_as_drf(exc)
        updates = data.model_dump(exclude_none=True)
        try:
            entry = config_service.update_config_entry(key=key, **updates)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ConfigEntryResponse.model_validate(entry).model_dump(mode="json"))

    @extend_schema(
        summary="Delete config entry",
        description="Deletes a config entry by key.",
        parameters=[
            OpenApiParameter(name="key", location=OpenApiParameter.PATH, type=str, description="Config entry key")
        ],
        responses={204: None, **_ERROR_RESPONSES},
    )
    def destroy(self, request: Request, key: str, **kwargs) -> Response:
        try:
            config_service.delete_config_entry(key=key)
        except ObjectDoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(list=extend_schema(tags=["Config Health"]))
class ConfigHealthViewSet(viewsets.ViewSet):
    """Configuration health: Django system checks tagged ``entirius_config``, computed on every read."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    access_area = "munin.config"
    # The recheck runs live probes (an SMTP login): POST stays a write, never a POST-read.
    access_levels = {"POST": "write"}

    @extend_schema(
        summary="Configuration health",
        description="Runs the config-only checks (no network probes except the cached toolbox status).",
        responses={200: ConfigHealthResponse, **_ERROR_RESPONSES},
    )
    def list(self, request: Request, **kwargs) -> Response:
        return self._respond(probe=False)

    @extend_schema(
        summary="Check again, with probes",
        description="Runs the config checks plus the live probes (tag `entirius_probe`, e.g. an SMTP login; each cached 60 s).",
        request=None,
        responses={200: ConfigHealthResponse, **_ERROR_RESPONSES},
        tags=["Config Health"],
    )
    def recheck(self, request: Request, **kwargs) -> Response:
        return self._respond(probe=True)

    @staticmethod
    def _respond(probe: bool) -> Response:
        response = ConfigHealthResponse(checked_at=timezone.now(), checks=health_service.collect(probe=probe))
        return Response(response.model_dump(mode="json"))
