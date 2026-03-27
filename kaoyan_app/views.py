from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import QuestionForm, QuestionSearchForm
from .models import Question, QuestionType


def is_admin(user):
    return user.is_staff


def question_list(request):
    """公开题目查询"""
    form = QuestionSearchForm(request.GET or None)
    questions = Question.objects.select_related("subject", "school", "question_type").all()

    if form.is_valid():
        subject = form.cleaned_data.get("subject")
        year = form.cleaned_data.get("year")
        school = form.cleaned_data.get("school")
        question_type = form.cleaned_data.get("question_type")
        difficulty = form.cleaned_data.get("difficulty")

        if subject:
            questions = questions.filter(subject=subject)
        if year:
            questions = questions.filter(year=year)
        if school:
            questions = questions.filter(school=school)
        if question_type:
            questions = questions.filter(question_type=question_type)
        if difficulty:
            questions = questions.filter(difficulty=difficulty)

    # 获取题型 ID（用于前端判断）
    choice_type_id = QuestionType.objects.filter(name="选择").values_list("id", flat=True).first()
    judge_type_id = QuestionType.objects.filter(name="判断").values_list("id", flat=True).first()

    # 兼容旧数据：将数组格式选项转为字典格式
    for q in questions:
        if q.options and isinstance(q.options, list):
            q.options = {chr(ord("A") + i): opt.split(". ", 1)[-1] if ". " in opt else opt
                         for i, opt in enumerate(q.options[:4])}

    # 分页：每页5题
    paginator = Paginator(questions, 5)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # 构建不含 page 的搜索参数字符串（分页链接用）
    search_params = request.GET.copy()
    search_params.pop("page", None)
    search_str = search_params.urlencode()

    return render(request, "kaoyan/question_list.html", {
        "form": form,
        "page_obj": page_obj,
        "search_str": search_str,
        "choice_type_id": choice_type_id,
        "judge_type_id": judge_type_id,
    })


@login_required
@user_passes_test(is_admin)
def question_add(request):
    """管理员添加题目"""
    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("kaoyan:question_add")
    else:
        form = QuestionForm()

    # 获取所有题型用于前端动态显示选项
    question_types = QuestionType.objects.all()
    choice_type_id = QuestionType.objects.filter(name="选择").values_list("id", flat=True).first()
    judge_type_id = QuestionType.objects.filter(name="判断").values_list("id", flat=True).first()

    return render(request, "kaoyan/question_form.html", {
        "form": form,
        "question_types": question_types,
        "choice_type_id": choice_type_id,
        "judge_type_id": judge_type_id,
    })


@login_required
@user_passes_test(is_admin)
def question_edit(request, pk):
    """管理员编辑题目"""
    question = get_object_or_404(Question, pk=pk)

    if request.method == "POST":
        form = QuestionForm(request.POST, request.FILES, instance=question)
        if form.is_valid():
            instance = form.save(commit=False)
            # 如果没选新文件，保留原图（super().save 可能会清空）
            if not request.FILES.get("image") and question.image:
                instance.image = question.image
            instance.save()
            return redirect("kaoyan:question_list")
    else:
        # 编辑时从字典拆分选项到四个字段
        initial = {}
        if question.options and isinstance(question.options, dict):
            for letter in ["a", "b", "c", "d"]:
                key = letter.upper()
                if key in question.options:
                    initial[f"option_{letter}"] = question.options[key]
        elif question.options and isinstance(question.options, list):
            # 兼容旧数据（数组格式）
            for i, opt in enumerate(question.options[:4]):
                letter = chr(ord("a") + i)
                prefix = letter.upper() + ". "
                text = opt
                if text.upper().startswith(prefix):
                    text = text[len(prefix):]
                initial[f"option_{letter}"] = text.strip()
        form = QuestionForm(instance=question, initial=initial)

    question_types = QuestionType.objects.all()
    choice_type_id = QuestionType.objects.filter(name="选择").values_list("id", flat=True).first()
    judge_type_id = QuestionType.objects.filter(name="判断").values_list("id", flat=True).first()

    return render(request, "kaoyan/question_form.html", {
        "form": form,
        "question": question,
        "question_types": question_types,
        "choice_type_id": choice_type_id,
        "judge_type_id": judge_type_id,
    })


@login_required
@user_passes_test(is_admin)
def question_delete(request, pk):
    """管理员删除题目"""
    question = get_object_or_404(Question, pk=pk)
    if request.method == "POST":
        question.delete()
        return redirect("kaoyan:question_list")
    return render(request, "kaoyan/question_confirm_delete.html", {"question": question})