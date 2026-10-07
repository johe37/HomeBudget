from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Hushållskalkyl"
admin.site.site_title = "Hushållskalkyl"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("budgets.urls")),
]
