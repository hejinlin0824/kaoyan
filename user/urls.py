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
    path("checkin-calendar/", views.checkin_calendar, name="checkin_calendar"),
    path("my-exams/", views.my_exams, name="my_exams"),
    path("profile/", views.profile, name="profile"),
    path("profile/<int:pk>/", views.profile, name="profile_detail"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("achievements/", views.achievements_page, name="achievements"),
]
