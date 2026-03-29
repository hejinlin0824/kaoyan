from django.urls import path
from . import views

app_name = "community"

urlpatterns = [
    path("question/<int:pk>/", views.question_discuss, name="question_discuss"),
    path("ai-question/<int:pk>/", views.ai_question_discuss, name="ai_question_discuss"),
    path("question/<int:pk>/comment/", views.add_comment, name="add_comment"),
    path("like/", views.toggle_like, name="toggle_like"),
    # 通知
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/unread/", views.notification_unread_count, name="notification_unread_count"),
    path("notifications/latest/", views.notification_latest, name="notification_latest"),
    path("notifications/mark-read/", views.notification_mark_read, name="notification_mark_read"),
    path("notifications/mark-all-read/", views.notification_mark_all_read, name="notification_mark_all_read"),
]
