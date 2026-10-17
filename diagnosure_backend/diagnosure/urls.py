from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve

FRONTEND_DIR = settings.BASE_DIR / "frontend"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # Frontend: landing page at "/" and the static pages/scripts in frontend/
    path("", serve, {"path": "diagnosure_final.html", "document_root": FRONTEND_DIR}),
    re_path(r"^(?P<path>[\w\-]+\.(?:html|js|css|png|jpg|jpeg|svg|ico))$", serve, {"document_root": FRONTEND_DIR}),
]
