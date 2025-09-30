from django.urls import path
from .views import dashboard_home, audit_logs_view

urlpatterns = [
    path('', dashboard_home, name='dashboard_home'),
    path('logs/', audit_logs_view, name='audit_logs'),
]


