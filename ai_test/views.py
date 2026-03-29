from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from kaoyan_app.models import QuestionType
from kaoyan_project.vip_utils import vip_required

from .forms import AIExamCreateForm, AIQuestionSearchForm, AIPracticeExamCreateForm
from .models import (
    AIGeneratedQuestion, AIExam, AIExamQuestion,
    AIPracticeExam, AIPracticeExamQuestion, AIWrongQuestion,
)

# 导入我们将要在下一步编写的异步任务
from .tasks import generate_ai_exam_task

# ─── AI题库组卷常量 ───
TYPE_FIELD_MAP = {
    "选择": "choice_count",
    "填空": "fill_count",
    "判断": "judge_count",
    "简答": "short_count",
    "计算": "calc_count",
    "画图": "draw_count",
}
SCORE_MAP = {"选择": 5, "填空": 5, "判断": 3, "简答": 0, "计算": 0, "画图": 0}
OBJECTIVE_TYPES = {"选择", "填空", "判断"}

# ─── 原有AI智能组卷视图 ───

@vip_required
def ai_exam_create(request):
    """
    AI智能组卷入口：
    接收前端配置，创建 pending 状态试卷记录，并将实际出题任务下发给异步队列
    """
    if request.method == "POST":
        form = AIExamCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                exam = AIExam.objects.create(
                    user=request.user,
                    status="pending",
                    subject=form.cleaned_data["subject"],
                    choice_count=form.cleaned_data.get("choice_count", 0),
                    fill_count=form.cleaned_data.get("fill_count", 0),
                    judge_count=form.cleaned_data.get("judge_count", 0),
                    short_count=form.cleaned_data.get("short_count", 0),
                    calc_count=form.cleaned_data.get("calc_count", 0),
                    draw_count=form.cleaned_data.get("draw_count", 0),
                )

            generate_ai_exam_task.delay(exam.id)
            return redirect("ai_test:ai_exam_list")
    else:
        form = AIExamCreateForm()

    return render(request, "ai_test/ai_exam_create.html", {"form": form})


@vip_required
def ai_exam_list(request):
    """
    用户的 AI 试卷列表：
    展示历史生成的 AI 试卷以及正在生成中的任务进度
    """
    exams = AIExam.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "ai_test/ai_exam_list.html", {"exams": exams})


@login_required
def ai_exam_status(request, pk):
    """
    状态轮询 API：
    供前端 AJAX 轮询调用，返回指定试卷的最新状态，以便动态更新 UI
    """
    exam = get_object_or_404(AIExam, pk=pk, user=request.user)
    return JsonResponse({
        "id": exam.id,
        "status": exam.status,
    })


@vip_required
def ai_exam_take(request, pk):
    """AI 变式出题作答：completed→taking(首次), taking→恢复, submitted→结果"""
    exam = get_object_or_404(AIExam, pk=pk, user=request.user)

    if exam.status == "pending":
        return redirect("ai_test:ai_exam_list")
    if exam.status == "submitted":
        return redirect("ai_test:ai_exam_result", exam.id)

    if exam.status == "completed":
        exam.status = "taking"
        exam.started_at = timezone.now()
        exam.save(update_fields=["status", "started_at"])

    eqs = exam.questions.select_related("question__school", "question__question_type").all()
    elapsed = 0
    if exam.started_at:
        elapsed = int((timezone.now() - exam.started_at).total_seconds())

    return render(request, "ai_test/ai_exam_take.html", {
        "exam": exam, "exam_questions": eqs, "elapsed_seconds": elapsed,
    })


@vip_required
def ai_exam_submit(request, pk):
    """AI 变式出题服务端提交 + 自动阅卷"""
    exam = get_object_or_404(AIExam, pk=pk, user=request.user)
    if exam.status == "submitted":
        return redirect("ai_test:ai_exam_result", exam.id)
    if exam.status != "taking" or request.method != "POST":
        return redirect("ai_test:ai_exam_take", exam.id)

    duration = int(request.POST.get("duration_seconds", 0))
    exam.duration_seconds = duration

    eqs = list(exam.questions.select_related("question").all())
    total_score = 0
    total_objective = 0
    wrong_questions = []

    for eq in eqs:
        q = eq.question
        type_name = q.question_type.name
        user_answer = request.POST.get(f"answer_{eq.id}", "").strip() or None
        eq.user_answer = user_answer

        if type_name not in OBJECTIVE_TYPES:
            eq.save(update_fields=["user_answer"])
            continue

        full_score = SCORE_MAP.get(type_name, 0)
        total_objective += full_score
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
                    is_correct = all(up.lower() == sp.lower() for up, sp in zip(user_parts, standard))
                elif len(user_parts) == 1 and len(standard) == 1:
                    is_correct = user_parts[0].lower() == standard[0].lower()

        if is_correct:
            total_score += full_score
        else:
            wrong_questions.append(eq)
        eq.save(update_fields=["user_answer"])

    exam.score = total_score
    exam.total_objective_score = total_objective
    exam.status = "submitted"
    exam.save(update_fields=["score", "total_objective_score", "duration_seconds", "status"])

    for eq in wrong_questions:
        obj, created = AIWrongQuestion.objects.get_or_create(user=request.user, question=eq.question)
        if not created:
            AIWrongQuestion.objects.filter(pk=obj.pk).update(error_count=F("error_count") + 1)

    total_q = exam.choice_count + exam.fill_count + exam.judge_count + exam.short_count + exam.calc_count + exam.draw_count
    from user.coin_utils import try_daily_checkin
    try_daily_checkin(request.user, question_count=total_q, objective_score=exam.score)

    return redirect("ai_test:ai_exam_result", exam.id)


@vip_required
def ai_exam_result(request, pk):
    """AI 变式出题阅卷结果"""
    exam = get_object_or_404(AIExam, pk=pk, user=request.user)
    if exam.status != "submitted":
        return redirect("ai_test:ai_exam_take", exam.id)
    eqs = exam.questions.select_related("question__school", "question__question_type").all()
    return render(request, "ai_test/ai_exam_result.html", {
        "exam": exam, "exam_questions": eqs,
    })


@login_required
def ai_question_list(request):
    """
    AI 题库浏览（免费可看列表，展示AI能力）：
    - 免费用户：可浏览题干列表，但点击查看答案/详情时拦截引导升级
    - VIP 用户：完全解锁
    """
    form = AIQuestionSearchForm(request.GET or None)
    questions = AIGeneratedQuestion.objects.select_related("school", "question_type").all()

    if form.is_valid():
        year = form.cleaned_data.get("year")
        school = form.cleaned_data.get("school")
        question_type = form.cleaned_data.get("question_type")
        difficulty = form.cleaned_data.get("difficulty")

        if year:
            questions = questions.filter(year=year)
        if school:
            questions = questions.filter(school=school)
        if question_type:
            questions = questions.filter(question_type=question_type)
        if difficulty:
            questions = questions.filter(difficulty=difficulty)

    choice_type_id = QuestionType.objects.filter(name="选择").values_list("id", flat=True).first()
    judge_type_id = QuestionType.objects.filter(name="判断").values_list("id", flat=True).first()

    is_vip = request.user.is_vip()

    paginator = Paginator(questions, 5)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    search_params = request.GET.copy()
    search_params.pop("page", None)
    search_str = search_params.urlencode()

    return render(request, "ai_test/ai_question_list.html", {
        "form": form,
        "page_obj": page_obj,
        "search_str": search_str,
        "choice_type_id": choice_type_id,
        "judge_type_id": judge_type_id,
        "is_vip": is_vip,
    })


# ─── AI题库组卷视图（新增） ───

@vip_required
def ai_practice_create(request):
    """AI题库组卷：从已有AI题库中不放回随机抽题"""
    if request.method == "POST":
        form = AIPracticeExamCreateForm(request.POST)
        if form.is_valid():
            counts = {k: form.cleaned_data[k] for k in TYPE_FIELD_MAP.values()}

            # 检查AI题库是否足够
            for type_name, field in TYPE_FIELD_MAP.items():
                needed = counts[field]
                if needed > 0:
                    available = AIGeneratedQuestion.objects.filter(
                        question_type__name=type_name
                    ).count()
                    if available < needed:
                        form.add_error(
                            field,
                            f"AI题库中{type_name}题仅 {available} 道，不够 {needed} 道"
                        )

            if form.errors:
                return render(request, "ai_test/ai_practice_create.html", {"form": form})

            with transaction.atomic():
                exam = AIPracticeExam.objects.create(user=request.user, **counts)
                order = 0
                for type_name, field in TYPE_FIELD_MAP.items():
                    needed = counts[field]
                    if needed > 0:
                        qs = list(
                            AIGeneratedQuestion.objects.filter(
                                question_type__name=type_name
                            )
                            .select_related("school", "question_type")
                            .order_by("?")[:needed]
                        )
                        for q in qs:
                            AIPracticeExamQuestion.objects.create(
                                exam=exam, question=q, order=order
                            )
                            order += 1

            return redirect("ai_test:ai_practice_preview", exam.id)
    else:
        form = AIPracticeExamCreateForm()

    return render(request, "ai_test/ai_practice_create.html", {"form": form})


@vip_required
def ai_practice_preview(request, pk):
    """AI题库练习卷预览"""
    exam = get_object_or_404(AIPracticeExam, pk=pk, user=request.user)
    eqs = exam.questions.select_related(
        "question__school", "question__question_type"
    ).all()
    return render(request, "ai_test/ai_practice_preview.html", {
        "exam": exam, "exam_questions": eqs
    })


@vip_required
def ai_practice_take(request, pk):
    """AI题库练习卷在线作答"""
    exam = get_object_or_404(AIPracticeExam, pk=pk, user=request.user)
    if exam.status == "submitted":
        return redirect("ai_test:ai_practice_result", exam.id)
    if exam.status == "preview":
        exam.status = "taking"
        exam.save(update_fields=["status"])

    eqs = exam.questions.select_related(
        "question__school", "question__question_type"
    ).all()
    return render(request, "ai_test/ai_practice_take.html", {
        "exam": exam, "exam_questions": eqs
    })


@vip_required
def ai_practice_submit(request, pk):
    """AI题库练习卷提交并自动阅卷"""
    exam = get_object_or_404(AIPracticeExam, pk=pk, user=request.user)
    if exam.status == "submitted":
        return redirect("ai_test:ai_practice_result", exam.id)
    if request.method != "POST":
        return redirect("ai_test:ai_practice_take", exam.id)

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

    # 错题入库
    for eq in wrong_questions:
        obj, created = AIWrongQuestion.objects.get_or_create(
            user=request.user,
            question=eq.question,
        )
        if not created:
            AIWrongQuestion.objects.filter(pk=obj.pk).update(error_count=F("error_count") + 1)

    # ── 每日打卡检测 ──
    total_question_count = exam.choice_count + exam.fill_count + exam.judge_count + exam.short_count + exam.calc_count + exam.draw_count
    from user.coin_utils import try_daily_checkin
    try_daily_checkin(request.user, question_count=total_question_count, objective_score=exam.score)

    return redirect("ai_test:ai_practice_result", exam.id)


@vip_required
def ai_practice_result(request, pk):
    """AI题库练习卷阅卷结果"""
    exam = get_object_or_404(AIPracticeExam, pk=pk, user=request.user)
    if exam.status != "submitted":
        return redirect("ai_test:ai_practice_take", exam.id)
    eqs = exam.questions.select_related(
        "question__school", "question__question_type"
    ).all()
    return render(request, "ai_test/ai_practice_result.html", {
        "exam": exam, "exam_questions": eqs
    })


@vip_required
def ai_practice_list(request):
    """AI题库练习卷列表"""
    exams = AIPracticeExam.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "ai_test/ai_practice_list.html", {"exams": exams})


@login_required
def ai_wrong_book(request):
    """
    AI错题本：
    - 免费用户：仅展示最近 10 道，底部引导升级
    - VIP 用户：完整错题本
    """
    wrongs_qs = AIWrongQuestion.objects.filter(
        user=request.user
    ).select_related("question__school", "question__question_type")

    is_vip = request.user.is_vip()
    total_count = wrongs_qs.count()

    if is_vip:
        from django.core.paginator import Paginator
        paginator = Paginator(wrongs_qs, 20)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)
        wrongs = page_obj
    else:
        wrongs = wrongs_qs[:10]
        page_obj = None

    return render(request, "ai_test/ai_wrong_book.html", {
        "wrong_questions": wrongs,
        "page_obj": page_obj,
        "total_count": total_count,
        "is_vip": is_vip,
    })
