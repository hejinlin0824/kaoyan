import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
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


@login_required
def checkin_calendar(request):
    """
    打卡日历：以日历形式可视化展示用户的打卡记录。
    支持 ?year=2026&month=3 参数切换月份。
    """
    import calendar
    from django.utils import timezone
    from .models import CoinRecord

    now = timezone.now()
    year = int(request.GET.get("year", now.year))
    month = int(request.GET.get("month", now.month))

    # 月份范围校验
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # 获取当月打卡日期集合
    checkin_records = CoinRecord.objects.filter(
        user=request.user,
        reason="daily_checkin",
        created_at__year=year,
        created_at__month=month,
    ).values_list("created_at", "description")

    checkin_dates = {}  # {day: description}
    for created_at, desc in checkin_records:
        day = created_at.day
        checkin_dates[day] = desc

    # 生成日历数据
    cal = calendar.Calendar(firstweekday=6)  # 周日开始
    month_days = cal.monthdayscalendar(year, month)

    # 月份名称
    month_name = f"{year}年{month}月"

    # 计算上/下月
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    # 统计当月打卡天数
    month_checkin_count = len(checkin_dates)

    # 统计总打卡天数（全量）
    total_checkin_count = CoinRecord.objects.filter(
        user=request.user,
        reason="daily_checkin",
    ).count()

    # 连续打卡天数
    streak = 0
    check_date = now.date()
    while True:
        if CoinRecord.objects.filter(
            user=request.user,
            reason="daily_checkin",
            created_at__date=check_date,
        ).exists():
            streak += 1
            from datetime import timedelta
            check_date -= timedelta(days=1)
        else:
            break

    return render(request, "user/checkin_calendar.html", {
        "month_name": month_name,
        "month_days": month_days,
        "checkin_dates": checkin_dates,
        "year": year,
        "month": month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "month_checkin_count": month_checkin_count,
        "total_checkin_count": total_checkin_count,
        "streak": streak,
        "user_coins": request.user.coins,
    })


@login_required
def my_exams(request):
    """我的考试：统一展示所有考试（真题组卷 + AI题库组卷 + AI变式出题）"""
    from zu_juan.models import Exam
    from ai_test.models import AIPracticeExam, AIExam

    user = request.user
    exams = []

    # 1. 真题组卷
    for e in Exam.objects.filter(user=user).order_by("-created_at"):
        q_count = e.questions.count()
        answered = e.questions.exclude(user_answer__isnull=True).exclude(user_answer__exact="").count()
        exams.append({
            "type": "真题组卷",
            "type_icon": "fa-book-open",
            "type_color": "var(--blue-600)",
            "type_bg": "var(--blue-50)",
            "id": e.id,
            "created_at": e.created_at,
            "status": e.status,
            "status_label": dict(Exam.STATUS_CHOICES).get(e.status, e.status),
            "q_count": q_count,
            "answered": answered,
            "score": e.score,
            "total_score": e.total_objective_score,
            "resume_url": f"/exam/take/{e.id}/" if e.status == "taking" else (
                f"/exam/preview/{e.id}/" if e.status == "preview" else f"/exam/result/{e.id}/"),
            "resume_label": "继续作答" if e.status == "taking" else (
                "开始考试" if e.status == "preview" else "查看成绩"),
        })

    # 2. AI题库组卷
    for e in AIPracticeExam.objects.filter(user=user).order_by("-created_at"):
        q_count = e.questions.count()
        answered = e.questions.exclude(user_answer__isnull=True).exclude(user_answer__exact="").count()
        exams.append({
            "type": "AI题库组卷",
            "type_icon": "fa-shuffle",
            "type_color": "#7c3aed",
            "type_bg": "#f5f3ff",
            "id": e.id,
            "created_at": e.created_at,
            "status": e.status,
            "status_label": dict(AIPracticeExam.STATUS_CHOICES).get(e.status, e.status),
            "q_count": q_count,
            "answered": answered,
            "score": e.score,
            "total_score": e.total_objective_score,
            "resume_url": f"/ai-test/practice/{e.id}/take/" if e.status == "taking" else (
                f"/ai-test/practice/{e.id}/preview/" if e.status == "preview" else f"/ai-test/practice/{e.id}/result/"),
            "resume_label": "继续作答" if e.status == "taking" else (
                "开始考试" if e.status == "preview" else "查看成绩"),
        })

    # 3. AI变式出题（异步）
    for e in AIExam.objects.filter(user=user).order_by("-created_at"):
        q_count = e.questions.count()
        answered = e.questions.exclude(user_answer__isnull=True).exclude(user_answer__exact="").count()
        if e.status == "pending":
            resume_url = None
            resume_label = "生成中..."
        elif e.status == "completed":
            resume_url = f"/ai-test/take/{e.id}/"
            resume_label = "开始练习"
        elif e.status == "taking":
            resume_url = f"/ai-test/take/{e.id}/"
            resume_label = "继续作答"
        else:  # submitted
            resume_url = f"/ai-test/result/{e.id}/"
            resume_label = "查看成绩"
        exams.append({
            "type": "AI变式出题",
            "type_icon": "fa-wand-magic-sparkles",
            "type_color": "#059669",
            "type_bg": "#f0fdf4",
            "id": e.id,
            "created_at": e.created_at,
            "status": e.status,
            "status_label": dict(AIExam.STATUS_CHOICES).get(e.status, e.status),
            "q_count": q_count,
            "answered": answered,
            "score": e.score,
            "total_score": e.total_objective_score,
            "resume_url": resume_url,
            "resume_label": resume_label,
        })

    # 按创建时间倒序
    exams.sort(key=lambda x: x["created_at"], reverse=True)

    # 分类
    in_progress = [e for e in exams if e["status"] in ("taking", "preview", "pending")]
    completed = [e for e in exams if e["status"] in ("submitted", "completed")]

    return render(request, "user/my_exams.html", {
        "in_progress": in_progress,
        "completed": completed,
        "has_active": any(e["status"] == "taking" for e in in_progress),
    })
