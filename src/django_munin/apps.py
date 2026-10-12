# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.apps import AppConfig


def discover_modules_after_migrate(sender, verbosity: int = 1, **kwargs) -> None:
    """post_migrate receiver — idempotent upsert of the Module table after every migrate."""
    from django_munin.services.discovery_service import scan_modules

    created, updated, deactivated = scan_modules()
    if verbosity >= 2:
        print(f"Munin: discovered modules ({created} created, {updated} updated, {deactivated} deactivated)")


class DjangoMuninConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_munin"
    verbose_name = "Munin"
    is_volkanos = True
    # Copied 1:1 from entirius-django-access cf538d2 catalogue defaults;
    # the access defaults stay until this module's release.
    access_areas = [
        {"key": "munin.config", "label": "Runtime configuration and health", "sensitive": ("config",)},
    ]
    # Every admin view carries its access_area; no route needs a path rule.
    access_route_rules = []

    def ready(self) -> None:
        from django.db.models.signals import post_delete, post_migrate, post_save

        from django_munin import checks
        from django_munin.models import ConfigEntry, Module
        from django_munin.services.config_service import invalidate_munin_cache

        post_save.connect(invalidate_munin_cache, sender=Module, dispatch_uid="munin.module.post_save")
        post_delete.connect(invalidate_munin_cache, sender=Module, dispatch_uid="munin.module.post_delete")
        post_save.connect(invalidate_munin_cache, sender=ConfigEntry, dispatch_uid="munin.config_entry.post_save")
        post_delete.connect(invalidate_munin_cache, sender=ConfigEntry, dispatch_uid="munin.config_entry.post_delete")
        post_migrate.connect(discover_modules_after_migrate, sender=self, dispatch_uid="munin.post_migrate.discover")
        checks.register()
