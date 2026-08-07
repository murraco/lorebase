from django.contrib import admin

from ingestion.models import Chunk


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "index", "heading_path", "token_count", "start_line", "end_line")
    list_filter = ("document__source",)
    search_fields = ("content", "heading_path")
