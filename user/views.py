import uuid

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegisterForm, PasswordResetRequestForm, PasswordResetConfirmForm, ProfileEditForm
from .models import User, PendingRegistration, CoinRecord


def home(request):
    from kaoyan_app.models import Question, School, QuestionType
    from django.utils import timezone
    from datetime import date

    user = request.user
    is_vip = user.is_vip() if user.is_authenticated else False
    vip_label = dict(user.VIP_CHOICES).get(user.vip_level, "") if user.is_authenticated else ""

    # 登录用户的扩展数据
    target_school_name = ""
    kaoyan_countdown = None
    kaoyan_session_label = ""
    study_days = 0
    streak = 0
    user_coins = 0

    if user.is_authenticated:
        user_coins = user.coins
        # 目标院校
        if user.target_school:
            target_school_name = user.target_school.name
        # 考研倒计时
        if user.kaoyan_session:
            session_dates = {27: date(2026, 12, 26), 28: date(2027, 12, 25), 29: date(2028, 12, 24), 30: date(2029, 12, 23)}
            target_date = session_dates.get(user.kaoyan_session)
            if target_date:
                delta = (target_date - timezone.localdate()).days
                kaoyan_countdown = max(delta, 0)
                kaoyan_session_label = f"第{user.kaoyan_session}届考研"
        # 学习天数
        if user.study_start_date:
            study_days = (timezone.localdate() - user.study_start_date).days + 1
        # 连续打卡
        from .coin_utils import get_streak
        streak = get_streak(user)

    return render(request, "user/home.html", {
        "user": user,
        "is_vip": is_vip,
        "vip_label": vip_label,
        "total_questions": Question.objects.count(),
        "total_schools": School.objects.count(),
        "total_types": QuestionType.objects.count(),
        "user_coins": user_coins,
        "target_school_name": target_school_name,
        "kaoyan_countdown": kaoyan_countdown,
        "kaoyan_session_label": kaoyan_session_label,
        "study_days": study_days,
        "streak": streak,
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
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse({"success": True}, status=200)
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

        # 登录失败 — AJAX 请求返回 JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            errors = {}
            for field in form:
                for err in field.errors:
                    errors.setdefault(field.name, []).append(err)
            for err in form.non_field_errors():
                errors.setdefault("__all__", []).append(err)
            return JsonResponse({"success": False, "errors": errors}, status=400)
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
    from .coin_utils import get_streak
    streak = get_streak(request.user)

    # 转盘状态
    from .coin_utils import can_daily_checkin
    has_checked_in_today = not can_daily_checkin(request.user)
    has_spun_today = CoinRecord.objects.filter(
        user=request.user, reason="wheel_spin", created_at__date=timezone.localdate(),
    ).exists()
    can_spin = has_checked_in_today and not has_spun_today

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
        "can_spin": can_spin,
        "has_checked_in_today": has_checked_in_today,
        "has_spun_today": has_spun_today,
    })


@login_required
@require_POST
def spin_wheel(request):
    """幸运转盘：打卡后可转一次"""
    import random
    from django.utils import timezone
    from .coin_utils import add_coins, can_daily_checkin
    from .models import CoinRecord

    # 必须今日已打卡
    if can_daily_checkin(request.user):
        return JsonResponse({"ok": False, "msg": "请先完成今日打卡"}, status=400)

    # 检查今日是否已转过
    today = timezone.localdate()
    if CoinRecord.objects.filter(
        user=request.user,
        reason="wheel_spin",
        created_at__date=today,
    ).exists():
        return JsonResponse({"ok": False, "msg": "今日已转过转盘"}, status=400)

    # 8 个奖品 & 概率（顺序与前端转盘一致）
    prizes = [
        {"name": "10 点数",          "type": "coin",  "value": 10,  "prob": 0.30},
        {"name": "好运签·逢考必过",   "type": "lucky", "value": 0,   "prob": 0.10},
        {"name": "50 点数",          "type": "coin",  "value": 50,  "prob": 0.20},
        {"name": "好运签·金榜题名",   "type": "lucky", "value": 0,   "prob": 0.10},
        {"name": "100 点数",         "type": "coin",  "value": 100, "prob": 0.05},
        {"name": "好运签·一战成硕",   "type": "lucky", "value": 0,   "prob": 0.10},
        {"name": "1天VIP",           "type": "vip",   "value": 1,   "prob": 0.05},
        {"name": "好运签·一战上岸",   "type": "lucky", "value": 0,   "prob": 0.10},
    ]

    # 加权随机
    r = random.random()
    cumulative = 0
    prize = prizes[-1]
    prize_index = len(prizes) - 1
    for i, p in enumerate(prizes):
        cumulative += p["prob"]
        if r <= cumulative:
            prize = p
            prize_index = i
            break

    # 发放奖励
    if prize["type"] == "coin":
        add_coins(request.user, prize["value"], reason="wheel_spin",
                  description=f"幸运转盘奖励：{prize['name']}")
    elif prize["type"] == "vip":
        request.user.extend_vip(prize["value"])
        CoinRecord.objects.create(
            user=request.user, amount=0, reason="wheel_spin",
            description=f"幸运转盘奖励：{prize['name']}",
        )
    else:
        # 好运签 — 纪念记录
        CoinRecord.objects.create(
            user=request.user, amount=0, reason="wheel_spin",
            description=f"幸运转盘：{prize['name']}",
        )

    return JsonResponse({
        "ok": True,
        "prize_index": prize_index,
        "prize_name": prize["name"],
        "prize_type": prize["type"],
        "prize_value": prize["value"],
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
    # 注意：AIExam 的 "completed" 表示"待练习"（题目已生成），应归为进行中
    in_progress = [e for e in exams if e["status"] in ("taking", "preview", "pending", "completed")]
    completed = [e for e in exams if e["status"] == "submitted"]

    return render(request, "user/my_exams.html", {
        "in_progress": in_progress,
        "completed": completed,
        "has_active": any(e["status"] == "taking" for e in in_progress),
    })


@login_required
def profile(request, pk=None):
    """个人主页：查看自己或他人的资料"""
    from django.utils import timezone

    if pk is None:
        user = request.user
    else:
        user = get_object_or_404(User, pk=pk)
    is_owner = (user == request.user)

    # 统计数据
    # 连续打卡天数
    from .coin_utils import get_streak
    streak = get_streak(user)

    # 总打卡天数
    total_checkins = CoinRecord.objects.filter(user=user, reason="daily_checkin").count()

    # 考试数
    from zu_juan.models import Exam
    from ai_test.models import AIPracticeExam, AIExam
    total_exams = (
        Exam.objects.filter(user=user).count()
        + AIPracticeExam.objects.filter(user=user).count()
        + AIExam.objects.filter(user=user, status__in=["completed", "taking", "submitted"]).count()
    )

    # 资源购买数
    from res_center.models import ResourcePurchase
    total_purchases = ResourcePurchase.objects.filter(user=user).count()

    # 注册天数
    from datetime import timedelta
    days_since_join = (timezone.localdate() - user.date_joined.date()).days + 1

    # 学习天数（从学习开始日期算起）
    study_days = 0
    if user.study_start_date:
        study_days = (timezone.localdate() - user.study_start_date).days + 1

    # 考研倒计时
    kaoyan_countdown = None
    kaoyan_session_label = ""
    if user.kaoyan_session:
        from datetime import date
        session_dates = {27: date(2026, 12, 26), 28: date(2027, 12, 25), 29: date(2028, 12, 24), 30: date(2029, 12, 23)}
        target_date = session_dates.get(user.kaoyan_session)
        if target_date:
            delta = (target_date - timezone.localdate()).days
            kaoyan_countdown = max(delta, 0)
            kaoyan_session_label = f"第{user.kaoyan_session}届考研"

    # 目标院校名称
    target_school_name = ""
    if user.target_school:
        target_school_name = user.target_school.name

    # 成就系统 - 计算已获得的成就
    from .models import Achievement
    earned_codes = set(Achievement.objects.filter(user=user).values_list("code", flat=True))

    # 检查并授予成就
    def grant_achievement(code, name, icon, desc):
        if code not in earned_codes:
            Achievement.objects.get_or_create(user=user, code=code, defaults={"name": name, "icon": icon, "description": desc})
            earned_codes.add(code)

    # 打卡成就
    if total_checkins >= 1:
        grant_achievement("first_checkin", "初来乍到", "fa-star", "完成第一次打卡")
    if streak >= 3:
        grant_achievement("streak_3", "坚持不懈", "fa-fire", "连续打卡3天")
    if streak >= 7:
        grant_achievement("streak_7", "一周达人", "fa-fire", "连续打卡7天")
    if streak >= 30:
        grant_achievement("streak_30", "月度之星", "fa-fire-flame-curved", "连续打卡30天")
    if streak >= 100:
        grant_achievement("streak_100", "百日传奇", "fa-fire-flame-curved", "连续打卡100天")
    if total_checkins >= 10:
        grant_achievement("checkin_10", "初露锋芒", "fa-medal", "累计打卡10天")
    if total_checkins >= 50:
        grant_achievement("checkin_50", "勤学苦练", "fa-medal", "累计打卡50天")
    if total_checkins >= 100:
        grant_achievement("checkin_100", "百日打卡", "fa-trophy", "累计打卡100天")
    # 考试成就
    if total_exams >= 1:
        grant_achievement("exam_1", "初试牛刀", "fa-file-pen", "完成第1套试卷")
    if total_exams >= 5:
        grant_achievement("exam_5", "小试牛刀", "fa-graduation-cap", "完成5套试卷")
    if total_exams >= 20:
        grant_achievement("exam_20", "练习达人", "fa-graduation-cap", "完成20套试卷")
    if total_exams >= 50:
        grant_achievement("exam_50", "题海战神", "fa-graduation-cap", "完成50套试卷")
    # VIP成就
    if user.is_vip():
        grant_achievement("vip_member", "尊贵会员", "fa-crown", "开通VIP会员")
    # 资源购买成就
    if total_purchases >= 1:
        grant_achievement("first_purchase", "资源新手", "fa-bag-shopping", "首次获取资源")
    if total_purchases >= 10:
        grant_achievement("purchase_10", "资源达人", "fa-bag-shopping", "获取10个资源")
    # 学习天数成就
    if study_days >= 30:
        grant_achievement("study_30", "学海无涯", "fa-book-open", "坚持学习30天")
    if study_days >= 100:
        grant_achievement("study_100", "百尺竿头", "fa-book-open", "坚持学习100天")
    if study_days >= 365:
        grant_achievement("study_365", "考研一年", "fa-calendar-check", "坚持学习365天")
    # 目标院校成就
    if user.target_school:
        grant_achievement("set_target", "明确目标", "fa-bullseye", "设置目标院校")

    # 所有成就定义（用于展示未获得的）
    all_achievements = [
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

    earned_count = len(earned_codes)
    total_count = len(all_achievements)

    return render(request, "user/profile.html", {
        "profile_user": user,
        "is_owner": is_owner,
        "streak": streak,
        "total_checkins": total_checkins,
        "total_exams": total_exams,
        "total_purchases": total_purchases,
        "days_since_join": days_since_join,
        "study_days": study_days,
        "kaoyan_countdown": kaoyan_countdown,
        "kaoyan_session_label": kaoyan_session_label,
        "target_school_name": target_school_name,
        "is_vip": user.is_vip(),
        "vip_label": dict(user.VIP_CHOICES).get(user.vip_level, ""),
        "all_achievements": all_achievements,
        "earned_codes": earned_codes,
        "earned_count": earned_count,
        "total_achievement_count": total_count,
    })


@login_required
def achievements_page(request):
    """成就系统独立页面：展示所有成就、达成要求、进度条"""
    from django.utils import timezone
    from .models import Achievement

    user = request.user

    # ── 统计数据 ──
    # 连续打卡天数
    from .coin_utils import get_streak
    streak = get_streak(user)

    # 总打卡天数
    total_checkins = CoinRecord.objects.filter(user=user, reason="daily_checkin").count()

    # 考试数
    from zu_juan.models import Exam
    from ai_test.models import AIPracticeExam, AIExam
    total_exams = (
        Exam.objects.filter(user=user).count()
        + AIPracticeExam.objects.filter(user=user).count()
        + AIExam.objects.filter(user=user, status__in=["completed", "taking", "submitted"]).count()
    )

    # 资源购买数
    from res_center.models import ResourcePurchase
    total_purchases = ResourcePurchase.objects.filter(user=user).count()

    # 学习天数
    study_days = 0
    if user.study_start_date:
        study_days = (timezone.localdate() - user.study_start_date).days + 1

    # 已获得成就的 code 集合
    earned_codes = set(Achievement.objects.filter(user=user).values_list("code", flat=True))

    # ── 成就定义 + 进度计算 ──
    # 每个成就: (code, name, icon, description, category, current_value, target_value)
    achievement_defs = [
        # 打卡类
        ("first_checkin", "初来乍到", "fa-star", "完成第一次打卡", "打卡", total_checkins, 1),
        ("streak_3", "坚持不懈", "fa-fire", "连续打卡3天", "打卡", streak, 3),
        ("streak_7", "一周达人", "fa-fire", "连续打卡7天", "打卡", streak, 7),
        ("streak_30", "月度之星", "fa-fire-flame-curved", "连续打卡30天", "打卡", streak, 30),
        ("streak_100", "百日传奇", "fa-fire-flame-curved", "连续打卡100天", "打卡", streak, 100),
        ("checkin_10", "初露锋芒", "fa-medal", "累计打卡10天", "打卡", total_checkins, 10),
        ("checkin_50", "勤学苦练", "fa-medal", "累计打卡50天", "打卡", total_checkins, 50),
        ("checkin_100", "百日打卡", "fa-trophy", "累计打卡100天", "打卡", total_checkins, 100),
        # 考试类
        ("exam_1", "初试牛刀", "fa-file-pen", "完成第1套试卷", "考试", total_exams, 1),
        ("exam_5", "小试牛刀", "fa-graduation-cap", "完成5套试卷", "考试", total_exams, 5),
        ("exam_20", "练习达人", "fa-graduation-cap", "完成20套试卷", "考试", total_exams, 20),
        ("exam_50", "题海战神", "fa-graduation-cap", "完成50套试卷", "考试", total_exams, 50),
        # VIP类
        ("vip_member", "尊贵会员", "fa-crown", "开通VIP会员", "其他", 1 if user.is_vip() else 0, 1),
        # 资源类
        ("first_purchase", "资源新手", "fa-bag-shopping", "首次获取资源", "资源", total_purchases, 1),
        ("purchase_10", "资源达人", "fa-bag-shopping", "获取10个资源", "资源", total_purchases, 10),
        # 学习天数类
        ("study_30", "学海无涯", "fa-book-open", "坚持学习30天", "学习", study_days, 30),
        ("study_100", "百尺竿头", "fa-book-open", "坚持学习100天", "学习", study_days, 100),
        ("study_365", "考研一年", "fa-calendar-check", "坚持学习365天", "学习", study_days, 365),
        # 目标类
        ("set_target", "明确目标", "fa-bullseye", "设置目标院校", "其他", 1 if user.target_school else 0, 1),
    ]

    # 按分类分组
    categories = {}
    for code, name, icon, desc, cat, current, target in achievement_defs:
        earned = code in earned_codes
        progress = min(100, int(current / target * 100)) if target > 0 else 0
        if earned:
            progress = 100
            current = target  # 已获得则显示满
        categories.setdefault(cat, []).append({
            "code": code,
            "name": name,
            "icon": icon,
            "description": desc,
            "earned": earned,
            "current": current,
            "target": target,
            "progress": progress,
        })

    # 总计
    earned_count = len(earned_codes)
    total_count = len(achievement_defs)

    return render(request, "user/achievements.html", {
        "categories": categories,
        "earned_count": earned_count,
        "total_count": total_count,
        "streak": streak,
        "total_checkins": total_checkins,
        "total_exams": total_exams,
        "total_purchases": total_purchases,
        "study_days": study_days,
    })


@login_required
def profile_edit(request):
    """编辑个人资料（防御性保存：只更新用户实际修改的字段）"""
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            original = request.user.__class__.objects.get(pk=request.user.pk)

            # 头像：没有上传新图片时保留原有头像
            if not form.cleaned_data.get("avatar"):
                user.avatar = original.avatar

            # 目标院校：未选择时保留原有值
            if not form.cleaned_data.get("target_school"):
                user.target_school = original.target_school

            # 考研届次：未选择时保留原有值
            if form.cleaned_data.get("kaoyan_session") is None:
                user.kaoyan_session = original.kaoyan_session

            # 学习开始日期：未填写时保留原有值
            if not form.cleaned_data.get("study_start_date"):
                user.study_start_date = original.study_start_date

            user.save()
            return redirect("user:profile")
    else:
        form = ProfileEditForm(instance=request.user)

    return render(request, "user/profile_edit.html", {
        "form": form,
    })
