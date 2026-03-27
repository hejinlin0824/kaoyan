from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import User


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


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "vip_level", "vip_start_date", "vip_expire_date", "is_vip_display", "is_active", "is_staff")
    list_filter = ("vip_level", "is_active", "is_staff")
    search_fields = ("username", "email")
    actions = [set_vip_7_days, set_vip_30_days, set_vip_60_days, set_vip_90_days, set_vip_180_days, set_vip_365_days, cancel_vip]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("VIP 信息", {"fields": ("vip_level", "vip_start_date", "vip_expire_date")}),
    )

    @admin.display(boolean=True, description="VIP有效")
    def is_vip_display(self, obj):
        return obj.is_vip()
    is_vip_display.short_description = "VIP有效"
