from django.urls import path

from . import views

app_name = "zu_juan"

urlpatterns = [
    path("create/", views.exam_create, name="exam_create"),
    path("preview/<int:pk>/", views.exam_preview, name="exam_preview"),
    path("take/<int:pk>/", views.exam_take, name="exam_take"),
    path("submit/<int:pk>/", views.exam_submit, name="exam_submit"),
    path("result/<int:pk>/", views.exam_result, name="exam_result"),
    path("wrong-book/", views.wrong_book, name="wrong_book"),
]