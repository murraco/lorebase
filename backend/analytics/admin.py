from django.contrib import admin

from analytics.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("message", "rating", "created_at")
    list_filter = ("rating", "message__conversation__workspace")
    search_fields = ("comment",)
