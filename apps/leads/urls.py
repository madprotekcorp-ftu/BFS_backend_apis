from django.urls import path

from . import views

urlpatterns = [
    path("public/enquiries/", views.EnquiryCreateView.as_view(), name="public-enquiry"),
    path("admin/dashboard/", views.DashboardView.as_view(), name="admin-dashboard"),
    path("admin/leads/", views.LeadListCreateView.as_view(), name="admin-leads"),
    path("admin/leads/export/", views.LeadExportView.as_view(), name="admin-leads-export"),
    path("admin/leads/<int:pk>/", views.LeadDetailView.as_view(), name="admin-lead-detail"),
    path("admin/leads/<int:pk>/remarks/", views.LeadRemarkListCreateView.as_view(), name="admin-lead-remarks"),
]
