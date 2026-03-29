from django.db import models
from django.conf import settings
from django.utils import timezone


class Notification(models.Model):
    """消息通知"""
    TYPE_CHOICES = [
        ("like", "点赞"),
        ("reply", "回复"),
        ("report_accepted", "纠错采纳"),
        ("report_rejected", "纠错驳回"),
        ("report_new", "新纠错"),
        ("resource_accepted", "资源投稿采纳"),
        ("resource_rejected", "资源投稿驳回"),
        ("resource_new", "新资源投稿"),
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


class ResourceSubmission(models.Model):
    """用户投稿资源（需管理员审核）"""
    STATUS_CHOICES = [
        ("pending", "待审核"),
        ("accepted", "已采纳"),
        ("rejected", "已驳回"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             verbose_name="投稿人", related_name="resource_submissions")
    title = models.CharField(max_length=200, verbose_name="标题")
    category = models.ForeignKey("res_center.ResourceCategory", on_delete=models.CASCADE,
                                 verbose_name="分类", related_name="submissions")
    subject = models.ForeignKey("kaoyan_app.Subject", on_delete=models.SET_NULL,
                                null=True, blank=True, verbose_name="关联专业课")
    school = models.ForeignKey("kaoyan_app.School", on_delete=models.SET_NULL,
                               null=True, blank=True, verbose_name="关联学校")
    cover = models.ImageField(upload_to="resource_submissions/%Y%m/", null=True, blank=True,
                              verbose_name="封面图片")
    description = models.TextField(verbose_name="简介")
    link = models.URLField(verbose_name="资源链接")
    price = models.PositiveIntegerField(default=0, verbose_name="价格（点数）",
                                        help_text="0 表示免费")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending",
                              verbose_name="状态")
    admin_note = models.TextField(blank=True, verbose_name="管理员备注/驳回原因")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name="审核人",
                                    related_name="reviewed_resource_submissions")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "资源投稿"
        verbose_name_plural = "资源投稿"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} 投稿: {self.title} ({self.status})"


class QuestionReport(models.Model):
    """题目纠错"""
    STATUS_CHOICES = [
        ("pending", "待审核"),
        ("accepted", "已采纳"),
        ("rejected", "已驳回"),
    ]
    SOURCE_CHOICES = [
        ("kaoyan", "真题"),
        ("ai", "AI题"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             verbose_name="报告人", related_name="question_reports")
    question_id = models.IntegerField(verbose_name="题目ID")
    question_source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="kaoyan",
                                       verbose_name="题目来源")
    description = models.TextField(verbose_name="纠错描述")
    image = models.ImageField(upload_to="report_images/", blank=True, null=True,
                              verbose_name="手写过程图片")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending",
                              verbose_name="状态")
    admin_note = models.TextField(blank=True, verbose_name="管理员备注/驳回原因")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, verbose_name="审核人",
                                    related_name="reviewed_reports")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="审核时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "题目纠错"
        verbose_name_plural = "题目纠错"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} 纠错(Q{self.question_id}): {self.status}"
