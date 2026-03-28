import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """自定义用户模型，增加 VIP 相关字段 + 邮箱验证"""

    VIP_CHOICES = [
        (0, "普通用户"),
        (1, "月度VIP"),
        (2, "季度VIP"),
        (3, "年度VIP"),
    ]

    vip_level = models.IntegerField(choices=VIP_CHOICES, default=0, verbose_name="VIP等级")
    vip_start_date = models.DateTimeField(null=True, blank=True, verbose_name="VIP开通时间")
    vip_expire_date = models.DateTimeField(null=True, blank=True, verbose_name="VIP过期时间")

    # ── 邮箱验证相关字段 ──
    email_verified = models.BooleanField(default=False, verbose_name="邮箱已验证")
    email_token = models.UUIDField(null=True, blank=True, verbose_name="验证令牌")

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def is_vip(self):
        """判断用户是否为有效 VIP"""
        if self.vip_level == 0:
            return False
        if self.vip_expire_date is None:
            return False
        from django.utils import timezone
        return self.vip_expire_date > timezone.now()

    def __str__(self):
        return self.username


class PendingRegistration(models.Model):
    """临时注册记录 — 用户点击邮箱验证链接后才会写入 User 表"""
    token = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="验证令牌")
    username = models.CharField(max_length=150, verbose_name="用户名")
    email = models.EmailField(verbose_name="邮箱")
    password_hash = models.CharField(max_length=128, verbose_name="密码哈希")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    used = models.BooleanField(default=False, verbose_name="已使用")

    class Meta:
        verbose_name = "待激活注册"
        verbose_name_plural = "待激活注册"

    def __str__(self):
        return f"{self.username} ({self.email})"
