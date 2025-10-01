from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "content", "moderation_result", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("user__username", "notes")
