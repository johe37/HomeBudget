from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("jamfor/", views.plan_compare, name="plan_compare"),
    path("exportera/", views.plan_export, name="plan_export"),
    path("importera/", views.plan_import, name="plan_import"),
    path("manad/ny/", views.plan_create, name="plan_create"),
    path("manad/exempel/", views.plan_sample, name="plan_sample"),
    path("manad/<int:pk>/", views.plan_edit, name="plan_edit"),
    path("manad/<int:pk>/kopiera/", views.plan_copy, name="plan_copy"),
    path("manad/<int:pk>/om/", views.plan_scenario_save, name="plan_scenario_save"),
    path("manad/<int:pk>/exportera/", views.plan_export_one, name="plan_export_one"),
    path("manad/<int:pk>/radera/", views.plan_delete, name="plan_delete"),
]
