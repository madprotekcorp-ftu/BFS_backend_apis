from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.catalog.urls")),
    path("api/", include("apps.leads.urls")),
    path("api/", include("apps.employees.urls")),
    path("api/", include("apps.imports.urls")),
    path("api/", include("apps.documents.urls")),
]

if settings.API_DOCS_ENABLED:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    ]

if settings.DJANGO_ADMIN_ENABLED:
    # Kept off /admin/ because the React app owns /admin/* routes.
    urlpatterns.append(path("django-admin/", admin.site.urls))

handler400 = "common.views.bad_request"
handler403 = "common.views.permission_denied"
handler404 = "common.views.not_found"
handler500 = "common.views.server_error"
