from django.urls import path
from . import views

urlpatterns = [
    path("user/", views.register_user),
    path("login/", views.login_user),
    path("analyze/", views.analyze),
    path("reports/<int:user_id>/", views.reports),
    path("family/", views.family),
]
