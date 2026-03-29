from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import User, CoinRecord, Achievement, PendingRegistration


@admin.action(description="开通VIP 7天")
def set_vip_7_days(modeladmin, request, queryset):
    for user in queryset:
        start = timezone.now()
        if user.vip_expire_date and user.vip_expire_date > start:
            start = user.vip_expire_date
        else:
            user.vip_start_date = start
        user.vip_level = 1
        user.vip_expire_date = start + timedelta(days=7)
        user.save()
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户开通7天VIP", messages.SUCCESS)


@admin.action(description="开通VIP 30天")
def set_vip_30_days(modeladmin, request, queryset):
    for user in queryset:
        start = timezone.now()
        if user.vip_expire_date and user.vip_expire_date > start:
            start = user.vip_expire_date
        else:
            user.vip_start_date = start
        user.vip_level = 1
        user.vip_expire_date = start + timedelta(days=30)
        user.save()
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户开通30天VIP", messages.SUCCESS)


@admin.action(description="开通VIP 60天")
def set_vip_60_days(modeladmin, request, queryset):
    for user in queryset:
        start = timezone.now()
        if user.vip_expire_date and user.vip_expire_date > start:
            start = user.vip_expire_date
        else:
            user.vip_start_date = start
        user.vip_level = 1
        user.vip_expire_date = start + timedelta(days=60)
        user.save()
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户开通60天VIP", messages.SUCCESS)


@admin.action(description="开通VIP 90天")
def set_vip_90_days(modeladmin, request, queryset):
    for user in queryset:
        start = timezone.now()
        if user.vip_expire_date and user.vip_expire_date > start:
            start = user.vip_expire_date
        else:
            user.vip_start_date = start
        user.vip_level = 2
        user.vip_expire_date = start + timedelta(days=90)
        user.save()
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户开通90天VIP", messages.SUCCESS)


@admin.action(description="开通VIP 180天")
def set_vip_180_days(modeladmin, request, queryset):
    for user in queryset:
        start = timezone.now()
        if user.vip_expire_date and user.vip_expire_date > start:
            start = user.vip_expire_date
        else:
            user.vip_start_date = start
        user.vip_level = 2
        user.vip_expire_date = start + timedelta(days=180)
        user.save()
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户开通180天VIP", messages.SUCCESS)


@admin.action(description="开通VIP 365天")
def set_vip_365_days(modeladmin, request, queryset):
    for user in queryset:
        start = timezone.now()
        if user.vip_expire_date and user.vip_expire_date > start:
            start = user.vip_expire_date
        else:
            user.vip_start_date = start
        user.vip_level = 3
        user.vip_expire_date = start + timedelta(days=365)
        user.save()
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户开通365天VIP", messages.SUCCESS)


@admin.action(description="取消VIP")
def cancel_vip(modeladmin, request, queryset):
    queryset.update(vip_level=0, vip_start_date=None, vip_expire_date=None)
    modeladmin.message_user(request, f"已取消 {queryset.count()} 个用户的VIP", messages.WARNING)


@admin.action(description="设置点数为 0")
def reset_coins(modeladmin, request, queryset):
    from .coin_utils import set_coins
    for user in queryset:
        set_coins(user, 0, description="管理员批量重置为0")
    modeladmin.message_user(request, f"已将 {queryset.count()} 个用户的点数重置为0", messages.SUCCESS)


@admin.action(description="增加 100 点数")
def add_coins_100(modeladmin, request, queryset):
    from .coin_utils import add_coins
    for user in queryset:
        add_coins(user, 100, reason="admin_adjust", description="管理员批量增加100点")
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户增加100点数", messages.SUCCESS)


@admin.action(description="增加 500 点数")
def add_coins_500(modeladmin, request, queryset):
    from .coin_utils import add_coins
    for user in queryset:
        add_coins(user, 500, reason="admin_adjust", description="管理员批量增加500点")
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户增加500点数", messages.SUCCESS)


@admin.action(description="增加 1000 点数")
def add_coins_1000(modeladmin, request, queryset):
    from .coin_utils import add_coins
    for user in queryset:
        add_coins(user, 1000, reason="admin_adjust", description="管理员批量增加1000点")
    modeladmin.message_user(request, f"已为 {queryset.count()} 个用户增加1000点数", messages.SUCCESS)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "email_verified", "coins", "vip_level", "vip_start_date", "vip_expire_date", "is_vip_display", "is_active", "is_staff")
    list_filter = ("vip_level", "is_active", "is_staff")
    search_fields = ("username", "email")
    actions = [set_vip_7_days, set_vip_30_days, set_vip_60_days, set_vip_90_days, set_vip_180_days, set_vip_365_days, cancel_vip, reset_coins, add_coins_100, add_coins_500, add_coins_1000]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("VIP 信息", {"fields": ("vip_level", "vip_start_date", "vip_expire_date")}),
        ("邮箱验证", {"fields": ("email_verified", "email_token")}),
        ("站内点数", {"fields": ("coins",)}),
        ("个人主页", {"fields": ("avatar", "bio")}),
        ("学习目标", {"fields": ("target_school", "kaoyan_session", "study_start_date")}),
    )

    @admin.display(boolean=True, description="VIP有效")
    def is_vip_display(self, obj):
        return obj.is_vip()
    is_vip_display.short_description = "VIP有效"


@admin.register(CoinRecord)
class CoinRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "reason", "description", "created_at")
    list_filter = ("reason", "created_at")
    search_fields = ("user__username", "description")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user",)
    ordering = ["-created_at"]

    def has_add_permission(self, request, obj=None):
        # 禁止手动添加记录，所有点数变动应通过 coin_utils 操作
        return False


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "name", "earned_at")
    list_filter = ("code",)
    search_fields = ("user__username", "name")


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "created_at", "used")
    list_filter = ("used",)
    search_fields = ("username", "email")
    readonly_fields = ("token", "created_at")
