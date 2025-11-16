from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup_view, name="signup"),
    # Organizations
    path("orgs/", views.org_list, name="org_list"),
    path("orgs/create/", views.org_create, name="org_create"),
    path("orgs/switch/<slug:slug>/", views.org_switch, name="org_switch"),
    path("orgs/<int:pk>/settings/", views.org_settings, name="org_settings"),
    path("orgs/<int:pk>/delete/", views.org_delete, name="org_delete"),
]
