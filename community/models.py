from django.db import models
from django.conf import settings


class Notification(models.Model):
    """消息通知"""
    TYPE_CHOICES = [
        ("like", "点赞"),
        ("reply", "回复"),
    ]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="notifications", verbose_name="接收者")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="sent_notifications", verbose_name="发送者")
    noti_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="通知类型")
    content = models.CharField(max_length=255, verbose_name="通知内容")
    url = models.CharField(max_length=500, blank=True, verbose_name="跳转链接")
    is_read = models.BooleanField(default=False, verbose_name="已读")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender.username} -> {self.recipient.username}: {self.content}"


class Comment(models.Model):
    """题目讨论评论"""
    SOURCE_CHOICES = [
        ("kaoyan", "真题"),
        ("ai", "AI题"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="评论者", related_name="community_comments")
    question_id = models.IntegerField(verbose_name="题目ID")
    question_source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="kaoyan", verbose_name="题目来源")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, verbose_name="父评论", related_name="replies")
    content = models.TextField(verbose_name="评论内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "评论"
        verbose_name_plural = "评论"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.content[:30]}"

    @property
    def is_reply(self):
        return self.parent is not None


class CommentLike(models.Model):
    """评论点赞"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, verbose_name="评论", related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "评论点赞"
        verbose_name_plural = "评论点赞"
        unique_together = ("user", "comment")

    def __str__(self):
        return f"{self.user.username} 点赞了 {self.comment.id}"