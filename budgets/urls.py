from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("manad/ny/", views.plan_create, name="plan_create"),
    path("manad/<int:pk>/", views.plan_edit, name="plan_edit"),
    path("manad/<int:pk>/kopiera/", views.plan_copy, name="plan_copy"),
    path("manad/<int:pk>/radera/", views.plan_delete, name="plan_delete"),
]
