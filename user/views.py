import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm, PasswordResetRequestForm, PasswordResetConfirmForm
from .models import User, PendingRegistration


def home(request):
    from kaoyan_app.models import Question, School, QuestionType
    user = request.user
    is_vip = user.is_vip() if user.is_authenticated else False
    vip_label = dict(user.VIP_CHOICES).get(user.vip_level, "") if user.is_authenticated else ""
    return render(request, "user/home.html", {
        "user": user,
        "is_vip": is_vip,
        "vip_label": vip_label,
        "total_questions": Question.objects.count(),
        "total_schools": School.objects.count(),
        "total_types": QuestionType.objects.count(),
    })


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password1"]

            # 检查用户名/邮箱是否已被正式注册
            if User.objects.filter(username=username).exists():
                form.add_error("username", "该用户名已被注册")
                return render(request, "user/register.html", {"form": form})
            if User.objects.filter(email__iexact=email).exists():
                form.add_error("email", "该邮箱已被注册")
                return render(request, "user/register.html", {"form": form})

            # 先删除同一邮箱的旧 PendingRegistration（允许重发）
            PendingRegistration.objects.filter(email__iexact=email, used=False).delete()

            # 创建待激活记录（不写 User 表！）
            from django.contrib.auth.hashers import make_password
            pending = PendingRegistration.objects.create(
                username=username,
                email=email,
                password_hash=make_password(password),
            )

            # 发送验证邮件
            try:
                current_site = get_current_site(request)
                verify_url = f"http://{current_site.domain}/verify-email/{pending.token}/"
                send_mail(
                    subject="厘米考研 — 激活你的账号",
                    message=(
                        f"你好 {username}！\n\n"
                        f"欢迎注册「厘米考研」！\n"
                        f"请点击以下链接完成邮箱验证：\n\n"
                        f"{verify_url}\n\n"
                        f"如果这不是你的操作，请忽略此邮件。\n"
                        f"— 厘米考研团队"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                # 邮件发送失败也允许继续，后续可重发
                pass
            return render(request, "user/register_pending.html", {"email": email})
    else:
        form = RegisterForm()
    return render(request, "user/register.html", {"form": form})


def verify_email(request, token):
    """邮箱验证：点击链接后才真正创建用户并自动登录（仅一次有效）"""
    try:
        pending = PendingRegistration.objects.get(token=token)
    except PendingRegistration.DoesNotExist:
        return render(request, "user/verify_email.html", {"status": "invalid"})

    if pending.used:
        return render(request, "user/verify_email.html", {"status": "used"})

    # 二次检查：防止在待激活期间用户名/邮箱被抢注
    if User.objects.filter(username=pending.username).exists():
        return render(request, "user/verify_email.html", {"status": "conflict", "field": "用户名"})
    if User.objects.filter(email__iexact=pending.email).exists():
        return render(request, "user/verify_email.html", {"status": "conflict", "field": "邮箱"})

    # ✅ 此时才真正写入 User 表
    user = User.objects.create_user(
        username=pending.username,
        email=pending.email,
        password=None,  # 先创建，再设密码
    )
    user.password = pending.password_hash  # 直接使用已哈希的密码
    user.email_verified = True
    user.is_active = True
    user.save()

    # 标记已使用
    pending.used = True
    pending.save(update_fields=["used"])

    # 自动登录（仅这一次）
    login(request, user)
    return render(request, "user/verify_email.html", {"status": "success", "user": user})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if not user.is_active:
                    form.add_error(None, "账号尚未激活，请先查收邮件完成邮箱验证。")
                else:
                    login(request, user)
                    return redirect("user:home")
            else:
                # 区分：用户名不存在 vs 密码错误 vs 账号未激活
                try:
                    db_user = User.objects.get(username=username)
                    if not db_user.is_active:
                        form.add_error(None, "账号尚未激活，请先查收邮件完成邮箱验证。")
                    else:
                        form.add_error(None, "密码错误，请重试。")
                except User.DoesNotExist:
                    # 也检查邮箱登录
                    try:
                        db_user = User.objects.get(email__iexact=username)
                        if not db_user.is_active:
                            form.add_error(None, "账号尚未激活，请先查收邮件完成邮箱验证。")
                        else:
                            form.add_error(None, "密码错误，请重试。")
                    except User.DoesNotExist:
                        form.add_error(None, "用户名或密码错误")
    else:
        form = LoginForm()
    return render(request, "user/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("user:home")


def password_reset_request(request):
    """忘记密码 - 输入邮箱，发送重置链接"""
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.get(email__iexact=email)
            token = uuid.uuid4()
            user.email_token = token
            user.save(update_fields=["email_token"])
            current_site = get_current_site(request)
            reset_url = f"http://{current_site.domain}/password-reset/{token}/"
            try:
                send_mail(
                    subject="厘米考研 — 密码重置",
                    message=(
                        f"你好 {user.username}！\n\n"
                        f"我们收到了你的密码重置请求。\n"
                        f"请点击以下链接设置新密码：\n\n"
                        f"{reset_url}\n\n"
                        f"如果这不是你的操作，请忽略此邮件。\n"
                        f"此链接仅可使用一次。\n\n"
                        f"— 厘米考研团队"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                pass
            return render(request, "user/password_reset_sent.html", {"email": email})
    else:
        form = PasswordResetRequestForm()
    return render(request, "user/password_reset_request.html", {"form": form})


def password_reset_confirm(request, token):
    """忘记密码 - 设置新密码"""
    try:
        user = User.objects.get(email_token=token)
    except User.DoesNotExist:
        return render(request, "user/password_reset_confirm.html", {"status": "invalid"})

    if request.method == "POST":
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["new_password"])
            user.email_token = None  # 清除 token，使链接失效
            user.save()
            return render(request, "user/password_reset_confirm.html", {"status": "success"})
    else:
        form = PasswordResetConfirmForm()
    return render(request, "user/password_reset_confirm.html", {"status": "form", "form": form})


def vip_page(request):
    """VIP 开通页面"""
    from django.templatetags.static import static
    return render(request, "user/vip.html", {
        "wechat_qrcode_url": static("images/wechat_qrcode.png"),
    })
