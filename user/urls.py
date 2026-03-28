from django.urls import path

from . import views

app_name = "user"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("vip/", views.vip_page, name="vip"),
    path("verify-email/<uuid:token>/", views.verify_email, name="verify_email"),
    path("password-reset/", views.password_reset_request, name="password_reset"),
    path("password-reset/<uuid:token>/", views.password_reset_confirm, name="password_reset_confirm"),
]
