import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from kaoyan_project.vip_utils import free_daily_limit, vip_required

from kaoyan_app.models import Question, QuestionType

from .forms import ExamCreateForm
from .models import Exam, ExamQuestion, WrongQuestion

# 题型名称 → 字段名 映射
TYPE_FIELD_MAP = {
    "选择": "choice_count",
    "填空": "fill_count",
    "判断": "judge_count",
    "简答": "short_count",
    "计算": "calc_count",
    "画图": "draw_count",
}

# 题型名称 → 满分
SCORE_MAP = {"选择": 5, "填空": 5, "判断": 3, "简答": 0, "计算": 0, "画图": 0}

# 客观题类型
OBJECTIVE_TYPES = {"选择", "填空", "判断"}


# ──────────────────────────────────────────
# 智能组卷模块
# ──────────────────────────────────────────

@free_daily_limit(limit=1)
def exam_create(request, **kwargs):
    """
    组卷入口：
    - 免费用户每天仅限 1 套
    - VIP 用户无限次
    """
    if request.method == "POST":
        form = ExamCreateForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data["subject"]
            counts = {k: form.cleaned_data[k] for k in TYPE_FIELD_MAP.values()}
            # 检查题库是否足够
            for type_name, field in TYPE_FIELD_MAP.items():
                needed = counts[field]
                if needed > 0:
                    available = Question.objects.filter(subject=subject, question_type__name=type_name).count()
                    if available < needed:
                        form.add_error(field, f"该专业课{type_name}题仅 {available} 道，不够 {needed} 道")
            if form.errors:
                return render(request, "zu_juan/exam_create.html", {"form": form})

            with transaction.atomic():
                exam = Exam.objects.create(user=request.user, **counts)
                order = 0
                for type_name, field in TYPE_FIELD_MAP.items():
                    needed = counts[field]
                    if needed > 0:
                        qs = list(Question.objects.filter(
                            subject=subject, question_type__name=type_name
                        ).select_related("school", "question_type").order_by("?")[:needed])
                        for q in qs:
                            ExamQuestion.objects.create(exam=exam, question=q, order=order)
                            order += 1
            return redirect("zu_juan:exam_preview", exam.id)
    else:
        form = ExamCreateForm()

    # 获取今日已用次数，供模板展示
    today = timezone.now().date()
    daily_count = Exam.objects.filter(user=request.user, created_at__date=today).count()

    return render(request, "zu_juan/exam_create.html", {
        "form": form,
        "daily_count": daily_count,
    })


@login_required
def exam_preview(request, pk):
    """试卷预览（不展示答案）"""
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    eqs = exam.questions.select_related("question__school", "question__question_type").all()
    return render(request, "zu_juan/exam_preview.html", {"exam": exam, "exam_questions": eqs})


@login_required
def exam_take(request, pk):
    """在线作答"""
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    if exam.status == "submitted":
        return redirect("zu_juan:exam_result", exam.id)
    if exam.status == "preview":
        exam.status = "taking"
        exam.save(update_fields=["status"])

    eqs = exam.questions.select_related("question__school", "question__question_type").all()
    return render(request, "zu_juan/exam_take.html", {"exam": exam, "exam_questions": eqs})


@login_required
def exam_submit(request, pk):
    """提交并自动阅卷"""
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    if exam.status == "submitted":
        return redirect("zu_juan:exam_result", exam.id)
    if request.method != "POST":
        return redirect("zu_juan:exam_take", exam.id)

    # 获取作答时长
    duration = int(request.POST.get("duration_seconds", 0))
    exam.duration_seconds = duration

    eqs = list(exam.questions.select_related("question").all())
    total_score = 0
    wrong_questions = []

    for eq in eqs:
        q = eq.question
        type_name = q.question_type.name
        field_name = f"answer_{eq.id}"
        user_answer = request.POST.get(field_name, "").strip() or None
        eq.user_answer = user_answer

        if type_name not in OBJECTIVE_TYPES:
            eq.is_correct = None
            eq.score = 0
            eq.save(update_fields=["user_answer", "is_correct", "score"])
            continue

        # 判分
        full_score = SCORE_MAP[type_name]
        correct_answer = (q.correct_answer or "").strip()
        is_correct = False

        if type_name == "选择":
            is_correct = user_answer and user_answer.upper() == correct_answer.upper()
        elif type_name == "判断":
            is_correct = user_answer and user_answer.strip() == correct_answer.strip()
        elif type_name == "填空":
            if correct_answer and user_answer:
                standard = [a.strip() for a in correct_answer.split(";") if a.strip()]
                user_parts = [a.strip() for a in user_answer.split(";") if a.strip()]
                if len(standard) == len(user_parts):
                    is_correct = all(
                        up.lower() == sp.lower() for up, sp in zip(user_parts, standard)
                    )
                elif len(user_parts) == 1 and len(standard) == 1:
                    is_correct = user_parts[0].lower() == standard[0].lower()

        eq.is_correct = is_correct
        eq.score = full_score if is_correct else 0
        total_score += eq.score
        eq.save(update_fields=["user_answer", "is_correct", "score"])

        if not is_correct:
            wrong_questions.append(eq)

    exam.score = total_score
    exam.total_objective_score = sum(
        SCORE_MAP.get(eq.question.question_type.name, 0) for eq in eqs
        if eq.question.question_type.name in OBJECTIVE_TYPES
    )
    exam.status = "submitted"
    exam.save(update_fields=["score", "total_objective_score", "duration_seconds", "status"])

    # 错题入库：首次创建 error_count=1，已存在则 +1
    from django.db.models import F
    for eq in wrong_questions:
        obj, created = WrongQuestion.objects.get_or_create(
            user=request.user,
            question=eq.question,
        )
        if not created:
            WrongQuestion.objects.filter(pk=obj.pk).update(error_count=F("error_count") + 1)

    # ── 每日打卡检测 ──
    # 只有今日尚未打卡时才显示打卡相关提示，已打卡则不提示
    total_question_count = exam.choice_count + exam.fill_count + exam.judge_count + exam.short_count + exam.calc_count + exam.draw_count
    from user.coin_utils import can_daily_checkin, try_daily_checkin
    if can_daily_checkin(request.user):
        success, msg = try_daily_checkin(request.user, question_count=total_question_count, objective_score=exam.score)
        if success:
            messages.success(request, f"🎉 打卡成功！{msg}")
        else:
            messages.warning(request, f"⚠️ 打卡未完成：{msg}")

    return redirect("zu_juan:exam_result", exam.id)


@login_required
def exam_result(request, pk):
    """
    阅卷结果：
    - VIP 用户：展示完整对错 + 正确答案 + 详细解析
    - 免费用户：仅展示客观题对错状态，隐藏答案与解析区域
    """
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    if exam.status != "submitted":
        return redirect("zu_juan:exam_take", exam.id)
    eqs = exam.questions.select_related("question__school", "question__question_type").all()
    # 刷新 F 表达式的值
    eqs = list(eqs)
    for eq in eqs:
        eq.question.correct_answer = eq.question.correct_answer  # ensure fresh

    is_vip = request.user.is_vip()

    return render(request, "zu_juan/exam_result.html", {
        "exam": exam,
        "exam_questions": eqs,
        "is_vip": is_vip,
    })


# ──────────────────────────────────────────
# 错题本模块
# ──────────────────────────────────────────

@login_required
def wrong_book(request):
    """
    错题本：
    - 免费用户：仅展示最近 10 道错题，底部引导升级 VIP
    - VIP 用户：完整错题本分页浏览 + 导出功能
    """
    wrongs_qs = WrongQuestion.objects.filter(
        user=request.user
    ).select_related("question__school", "question__question_type")

    is_vip = request.user.is_vip()
    total_count = wrongs_qs.count()

    if is_vip:
        # VIP：完整分页
        from django.core.paginator import Paginator
        paginator = Paginator(wrongs_qs, 20)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        wrongs = page_obj
    else:
        # 免费用户：仅展示最近 10 道
        wrongs = wrongs_qs[:10]
        page_obj = None

    return render(request, "zu_juan/wrong_book.html", {
        "wrong_questions": wrongs,
        "page_obj": page_obj,
        "total_count": total_count,
        "is_vip": is_vip,
    })


@vip_required
def wrong_book_export(request):
    """错题本导出（VIP 专属）：生成可打印的 HTML 视图"""
    wrongs = WrongQuestion.objects.filter(
        user=request.user
    ).select_related("question__school", "question__question_type").all()

    return render(request, "zu_juan/wrong_book_export.html", {
        "wrong_questions": wrongs,
        "username": request.user.username,
    })