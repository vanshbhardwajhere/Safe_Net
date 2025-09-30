from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from .forms import AuditLogFilterForm
from .models import AuditLog
from moderation.models import Content, ModerationResult
from moderation.forms import ContentForm


# ✅ Dashboard home
@login_required
def dashboard_home(request):
    total_content = Content.objects.count()
    flagged_content = Content.objects.filter(status="flagged").count()
    banned_users = request.user.__class__.objects.filter(is_banned=True).count()

    stats = {
        "total_content": total_content,
        "flagged_content": flagged_content,
        "banned_users": banned_users,
    }
    recent_comments = Content.objects.order_by("-created_at")[:10]
    form = ContentForm()
    return render(
        request,
        "dashboard/home.html",
        {"stats": stats, "recent_comments": recent_comments, "form": form},
    )


# ✅ View and filter audit logs
@login_required
def audit_logs_view(request):
    form = AuditLogFilterForm(request.GET or None)
    logs = AuditLog.objects.all().order_by("-timestamp")

    if form.is_valid():
        action = form.cleaned_data.get("action")
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")

        if action:
            logs = logs.filter(action=action)
        if start_date:
            logs = logs.filter(timestamp__date__gte=start_date)
        if end_date:
            logs = logs.filter(timestamp__date__lte=end_date)

    return render(request, "dashboard/audit_logs.html", {"logs": logs, "form": form})
