from django.urls import path

from . import views

urlpatterns = [
    path("admin/leads/import/", views.ImportUploadView.as_view(), name="admin-import-upload"),
    path("admin/leads/import/template/", views.ImportTemplateView.as_view(), name="admin-import-template"),
    path("admin/leads/import/<uuid:batch_id>/", views.ImportBatchDetailView.as_view(), name="admin-import-detail"),
    path(
        "admin/leads/import/<uuid:batch_id>/confirm/", views.ImportConfirmView.as_view(), name="admin-import-confirm"
    ),
    path("admin/leads/import/<uuid:batch_id>/cancel/", views.ImportCancelView.as_view(), name="admin-import-cancel"),
    path("admin/leads/import/<uuid:batch_id>/report/", views.ImportReportView.as_view(), name="admin-import-report"),
]
