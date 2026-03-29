from django.contrib import admin
from .models import Comment, CommentLike, Notification

admin.site.register(Comment)
admin.site.register(CommentLike)
admin.site.register(Notification)
