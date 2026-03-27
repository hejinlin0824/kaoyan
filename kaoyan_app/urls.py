from django.urls import path

from . import views

app_name = "kaoyan"

urlpatterns = [
    path("questions/", views.question_list, name="question_list"),
    path("questions/add/", views.question_add, name="question_add"),
    path("questions/<int:pk>/edit/", views.question_edit, name="question_edit"),
    path("questions/<int:pk>/delete/", views.question_delete, name="question_delete"),
]