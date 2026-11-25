from django.urls import path

from . import views

urlpatterns = [
    path("admin/leads/<int:pk>/documents/", views.LeadDocumentListCreateView.as_view(), name="admin-lead-documents"),
    path("admin/documents/bin/", views.DocumentBinListView.as_view(), name="admin-document-bin"),
    path("admin/documents/<uuid:document_id>/", views.DocumentDeleteView.as_view(), name="admin-document-delete"),
    path(
        "admin/documents/<uuid:document_id>/download/",
        views.DocumentDownloadView.as_view(),
        name="admin-document-download",
    ),
    path(
        "admin/documents/<uuid:document_id>/restore/",
        views.DocumentRestoreView.as_view(),
        name="admin-document-restore",
    ),
    path("admin/documents/<uuid:document_id>/purge/", views.DocumentPurgeView.as_view(), name="admin-document-purge"),
]
