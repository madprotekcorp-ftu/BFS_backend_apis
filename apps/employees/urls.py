from django.urls import path

from . import views

urlpatterns = [
    path("admin/employees/", views.EmployeeListCreateView.as_view(), name="admin-employees"),
    path("admin/employees/<int:pk>/", views.EmployeeDetailView.as_view(), name="admin-employee-detail"),
    path("admin/leads/<int:pk>/assign/", views.LeadAssignView.as_view(), name="admin-lead-assign"),
    path(
        "admin/leads/<int:pk>/assignments/",
        views.LeadAssignmentListView.as_view(),
        name="admin-lead-assignments",
    ),
]
