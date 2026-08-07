from django.contrib import admin

from rag.models import Citation, Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "latency_ms", "input_tokens", "output_tokens", "cost")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "workspace", "user", "created_at")
    list_filter = ("workspace",)
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "created_at", "latency_ms", "cost")
    list_filter = ("role", "conversation__workspace")
    search_fields = ("content",)


@admin.register(Citation)
class CitationAdmin(admin.ModelAdmin):
    list_display = ("message", "chunk")
    list_filter = ("message__conversation__workspace",)
