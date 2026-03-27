from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

# 复用原有的 VIP 权限校验装饰器
from zu_juan.views import vip_required

from .forms import AIExamCreateForm
from .models import AIExam, AIExamQuestion

# 导入我们将要在下一步编写的异步任务
from .tasks import generate_ai_exam_task


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
                # 1. 创建处于 pending (进行中) 状态的试卷记录
                exam = AIExam.objects.create(
                    user=request.user,
                    status="pending",
                    choice_count=form.cleaned_data.get("choice_count", 0),
                    fill_count=form.cleaned_data.get("fill_count", 0),
                    judge_count=form.cleaned_data.get("judge_count", 0),
                    short_count=form.cleaned_data.get("short_count", 0),
                    calc_count=form.cleaned_data.get("calc_count", 0),
                    draw_count=form.cleaned_data.get("draw_count", 0),
                )
            
            # 2. 触发异步大模型出题任务 (非阻塞)
            # 使用 Celery 标准的 delay 方法异步执行
            generate_ai_exam_task.delay(exam.id)
            
            # 3. 任务下发后，立即跳转到试卷列表页查看进度
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
    """
    AI 试卷作答/练习页面：
    交互流程与常规抽题组卷一致，但无底部的打分/提交逻辑，纯净练习。
    """
    exam = get_object_or_404(AIExam, pk=pk, user=request.user)
    
    # 防御性编程：如果试卷还在生成中，禁止进入作答页面，强制退回列表页
    if exam.status == "pending":
        return redirect("ai_test:ai_exam_list")
        
    # 获取该试卷所有的 AI 变式题目
    eqs = exam.questions.select_related("question__school", "question__question_type").all()
    
    return render(request, "ai_test/ai_exam_take.html", {
        "exam": exam,
        "exam_questions": eqs
    })