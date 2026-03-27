from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """自定义用户模型，增加 VIP 相关字段"""

    VIP_CHOICES = [
        (0, "普通用户"),
        (1, "月度VIP"),
        (2, "季度VIP"),
        (3, "年度VIP"),
    ]

    vip_level = models.IntegerField(choices=VIP_CHOICES, default=0, verbose_name="VIP等级")
    vip_start_date = models.DateTimeField(null=True, blank=True, verbose_name="VIP开通时间")
    vip_expire_date = models.DateTimeField(null=True, blank=True, verbose_name="VIP过期时间")

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