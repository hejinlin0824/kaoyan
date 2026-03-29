import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """自定义用户模型，增加 VIP 相关字段 + 邮箱验证 + 站内点数"""

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

    # ── 站内点数 ──
    coins = models.IntegerField(default=0, verbose_name="站内点数")

    # ── 个人主页 ──
    avatar = models.ImageField(upload_to="avatars/", default="avatars/default.png", verbose_name="头像")
    bio = models.TextField(max_length=300, blank=True, default="", verbose_name="个人简介")

    # ── 学习目标 ──
    target_school = models.ForeignKey(
        "kaoyan_app.School", on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="目标院校"
    )
    KAOYAN_SESSION_CHOICES = [
        (27, "第27届考研（2026年12月）"),
        (28, "第28届考研（2027年12月）"),
        (29, "第29届考研（2028年12月）"),
        (30, "第30届考研（2029年12月）"),
    ]
    kaoyan_session = models.IntegerField(
        choices=KAOYAN_SESSION_CHOICES, null=True, blank=True, verbose_name="考研届次"
    )
    study_start_date = models.DateField(null=True, blank=True, verbose_name="学习开始日期")

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

    def extend_vip(self, days):
        """延长 VIP 天数，如果没有 VIP 则开通"""
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        if self.is_vip():
            self.vip_expire_date = self.vip_expire_date + timedelta(days=days)
        else:
            self.vip_level = 1
            self.vip_start_date = now
            self.vip_expire_date = now + timedelta(days=days)
        self.save(update_fields=["vip_level", "vip_start_date", "vip_expire_date"])

    def __str__(self):
        return self.username


class CoinRecord(models.Model):
    """站内点数变动记录"""
    REASON_CHOICES = [
        ("daily_checkin", "每日打卡"),
        ("wheel_spin", "幸运转盘"),
        ("admin_adjust", "管理员调整"),
        ("reward", "系统奖励"),
        ("consume", "消费扣除"),
        ("other", "其他"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coin_records", verbose_name="用户")
    amount = models.IntegerField(verbose_name="变动数量", help_text="正数为增加，负数为扣除")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default="other", verbose_name="变动原因")
    description = models.CharField(max_length=200, blank=True, default="", verbose_name="说明")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "点数记录"
        verbose_name_plural = "点数记录"
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.amount >= 0 else ""
        return f"{self.user.username} {sign}{self.amount} ({self.get_reason_display()})"


class Achievement(models.Model):
    """成就系统"""
    ACHIEVEMENT_CHOICES = [
        ("first_checkin", "初来乍到", "fa-star", "完成第一次打卡"),
        ("streak_3", "坚持不懈", "fa-fire", "连续打卡3天"),
        ("streak_7", "一周达人", "fa-fire", "连续打卡7天"),
        ("streak_30", "月度之星", "fa-fire-flame-curved", "连续打卡30天"),
        ("streak_100", "百日传奇", "fa-fire-flame-curved", "连续打卡100天"),
        ("checkin_10", "初露锋芒", "fa-medal", "累计打卡10天"),
        ("checkin_50", "勤学苦练", "fa-medal", "累计打卡50天"),
        ("checkin_100", "百日打卡", "fa-trophy", "累计打卡100天"),
        ("exam_1", "初试牛刀", "fa-file-pen", "完成第1套试卷"),
        ("exam_5", "小试牛刀", "fa-graduation-cap", "完成5套试卷"),
        ("exam_20", "练习达人", "fa-graduation-cap", "完成20套试卷"),
        ("exam_50", "题海战神", "fa-graduation-cap", "完成50套试卷"),
        ("vip_member", "尊贵会员", "fa-crown", "开通VIP会员"),
        ("first_purchase", "资源新手", "fa-bag-shopping", "首次获取资源"),
        ("purchase_10", "资源达人", "fa-bag-shopping", "获取10个资源"),
        ("study_30", "学海无涯", "fa-book-open", "坚持学习30天"),
        ("study_100", "百尺竿头", "fa-book-open", "坚持学习100天"),
        ("study_365", "考研一年", "fa-calendar-check", "坚持学习365天"),
        ("set_target", "明确目标", "fa-bullseye", "设置目标院校"),
    ]

    code = models.CharField(max_length=30, verbose_name="成就代码")
    name = models.CharField(max_length=30, verbose_name="成就名称")
    icon = models.CharField(max_length=30, verbose_name="图标")
    description = models.CharField(max_length=100, verbose_name="描述")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="achievements", verbose_name="用户")
    earned_at = models.DateTimeField(auto_now_add=True, verbose_name="获得时间")

    class Meta:
        verbose_name = "成就"
        verbose_name_plural = "成就"
        unique_together = ("user", "code")
        ordering = ["-earned_at"]

    def __str__(self):
        return f"{self.user.username} - {self.name}"


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
