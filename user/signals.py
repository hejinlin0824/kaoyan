from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def grant_trial_vip(sender, instance, created, **kwargs):
    """
    新用户注册成功后，自动发放 1 天体验 VIP 权限。
    设置 vip_level=1（月度VIP级别），有效期1天。
    """
    if created:
        from django.utils import timezone
        instance.vip_level = 1  # 使用整数，与 VIP_CHOICES 对应
        instance.vip_start_date = timezone.now()
        instance.vip_expire_date = timezone.now() + timedelta(days=1)
        instance.save(update_fields=["vip_level", "vip_start_date", "vip_expire_date"])