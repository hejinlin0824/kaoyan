"""
全局 VIP 权限工具模块
提供装饰器、上下文处理器等公共能力，供各 app 复用。
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


# ──────────────────────────────────────────
# 装饰器
# ──────────────────────────────────────────

def vip_required(view_func):
    """
    VIP 专属装饰器：非 VIP 用户将被优雅地引导到 /vip/ 页面，
    并附带 ?from=<app_name> 参数，方便 VIP 页面展示针对性提示。
    """
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_vip():
            return redirect(
                reverse("user:vip") + "?from=" + view_func.__name__
            )
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    wrapper.__doc__ = view_func.__doc__
    return wrapper


def free_daily_limit(limit=1):
    """
    免费用户每日限额装饰器工厂。
    VIP 用户不受限制；免费用户超过每日限额后重定向到 VIP 页面。

    用法：
        @free_daily_limit(limit=1)
        def exam_create(request):
            ...

    被装饰的 view 函数需要接受一个额外参数 daily_count（通过 kwargs 注入），
    也可以忽略它。
    """
    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_vip():
                return view_func(request, *args, **kwargs)

            # 免费用户：统计今日已创建数量
            today = timezone.now().date()
            model = _guess_model(view_func)
            if model:
                count = model.objects.filter(
                    user=request.user,
                    created_at__date=today,
                ).count()
            else:
                count = 0

            if count >= limit:
                return redirect(
                    reverse("user:vip")
                    + f"?from={view_func.__name__}&reason=daily_limit"
                )

            kwargs["daily_count"] = count
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        wrapper.__doc__ = view_func.__doc__
        return wrapper
    return decorator


def _guess_model(view_func):
    """根据视图函数所在模块推断对应的 Model"""
    module = view_func.__module__
    if "zu_juan" in module:
        from zu_juan.models import Exam
        return Exam
    elif "ai_test" in module:
        from ai_test.models import AIPracticeExam
        return AIPracticeExam
    return None


# ──────────────────────────────────────────
# 上下文处理器（让所有模板都能访问 VIP 状态）
# ──────────────────────────────────────────

def vip_context(request):
    """
    全局模板上下文处理器：注入 is_vip / vip_label / is_free_user / user_coins。
    在 settings.py TEMPLATES → OPTIONS → context_processors 中注册即可。
    """
    user = request.user
    if user.is_authenticated:
        is_vip = user.is_vip()
        vip_label = dict(user.VIP_CHOICES).get(user.vip_level, "")
        return {
            "is_vip": is_vip,
            "vip_label": vip_label,
            "is_free_user": not is_vip,
            "user_coins": user.coins,
        }
    return {
        "is_vip": False,
        "vip_label": "",
        "is_free_user": True,
        "user_coins": 0,
    }
