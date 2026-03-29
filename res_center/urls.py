from django.urls import path
from . import views

app_name = "res_center"

urlpatterns = [
    path("", views.resource_list, name="list"),
    path("<int:pk>/", views.resource_detail, name="detail"),
    path("<int:pk>/purchase/", views.resource_purchase, name="purchase"),
    path("upload/", views.resource_upload, name="upload"),
    path("<int:pk>/edit/", views.resource_edit, name="edit"),
    path("submit/", views.resource_submit, name="submit"),
    path("my-submissions/", views.my_submissions, name="my_submissions"),
    path("my/", views.my_purchases, name="my_purchases"),
]
