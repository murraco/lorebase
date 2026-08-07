from django.contrib import admin

from sources.models import Document, Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "type", "status", "last_synced_at")
    list_filter = ("type", "status", "workspace")
    search_fields = ("name",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "source", "version", "deleted", "updated_at")
    list_filter = ("source", "deleted")
    search_fields = ("title", "path", "external_id")
