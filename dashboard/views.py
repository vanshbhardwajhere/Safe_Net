from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from .forms import AuditLogFilterForm
from .models import AuditLog
from moderation.models import Content, ModerationResult
from moderation.forms import ContentForm
from users.models import User


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


# ✅ Admin: Manage users
@login_required
def manage_users_view(request):
    # Check if user is admin
    if request.user.role != 'admin':
        messages.error(request, "You don't have permission to manage users.")
        return redirect("dashboard_home")
    
    users = User.objects.all().order_by('-date_joined')
    return render(request, "dashboard/manage_users.html", {"users": users})


# ✅ Admin: Ban/Unban user
@login_required
def toggle_user_ban_view(request, user_id):
    if request.user.role != 'admin':
        messages.error(request, "You don't have permission to ban users.")
        return redirect("dashboard_home")
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == "POST":
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')
        
        if action == 'ban':
            user.is_banned = True
            user.save()
            messages.warning(request, f"User {user.username} has been banned.")
            
            # Log the action
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action='banned_user',
                    notes=f'Banned user {user.username}: {reason}' if reason else f'Banned user {user.username}'
                )
            except Exception:
                pass
                
        elif action == 'unban':
            user.is_banned = False
            user.save()
            messages.success(request, f"User {user.username} has been unbanned.")
            
            # Log the action
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action='unbanned_user',
                    notes=f'Unbanned user {user.username}: {reason}' if reason else f'Unbanned user {user.username}'
                )
            except Exception:
                pass
        
        return redirect("manage_users")
    
    return render(request, "dashboard/toggle_user_ban.html", {"target_user": user})
