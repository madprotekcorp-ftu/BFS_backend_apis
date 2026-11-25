from django.urls import path

from . import views

urlpatterns = [
    path("services/", views.PublicServiceListView.as_view(), name="public-services"),
]
