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
    # 纠错
    path("report/<int:pk>/", views.submit_report, name="submit_report"),
    path("reports/", views.report_list, name="report_list"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
    path("reports/<int:pk>/review/", views.report_review, name="report_review"),
    # 审核中心
    path("review-center/", views.review_center, name="review_center"),
    # 资源投稿审核
    path("resource-submissions/", views.resource_submission_list, name="resource_submission_list"),
    path("resource-submissions/<int:pk>/", views.resource_submission_detail, name="resource_submission_detail"),
    path("resource-submissions/<int:pk>/review/", views.resource_submission_review, name="resource_submission_review"),
]
