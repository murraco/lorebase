from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import ApiKey, Membership, User, Workspace

admin.site.register(User, UserAdmin)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "created_at")
    list_filter = ("role", "workspace")
    search_fields = ("user__username", "workspace__name")


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    # key_hash deliberately absent: the admin is for revoking/auditing
    # keys, never for looking one up.
    list_display = ("name", "membership", "last_used_at", "created_at")
    list_filter = ("membership__workspace",)
    search_fields = ("name", "membership__user__username")
