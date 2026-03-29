from django.urls import path

from . import views

app_name = "ai_test"

urlpatterns = [
    # AI 智能组卷配置与生成入口（异步LLM）
    path("create/", views.ai_exam_create, name="ai_exam_create"),

    # 用户的 AI 试卷列表（用于查看进度状态和历史记录）
    path("list/", views.ai_exam_list, name="ai_exam_list"),

    # 异步任务状态轮询接口 (供前端 AJAX 调用，返回 JSON)
    path("status/<int:pk>/", views.ai_exam_status, name="ai_exam_status"),

    # AI 试卷作答页面
    path("take/<int:pk>/", views.ai_exam_take, name="ai_exam_take"),
    # AI 试卷提交阅卷
    path("submit/<int:pk>/", views.ai_exam_submit, name="ai_exam_submit"),
    # AI 试卷阅卷结果
    path("result/<int:pk>/", views.ai_exam_result, name="ai_exam_result"),

    # AI 题库浏览（与真题题库并行，展示所有 AI 变式题目）
    path("questions/", views.ai_question_list, name="ai_question_list"),

    # ─── AI题库组卷（同步抽题，新增） ───
    path("practice/create/", views.ai_practice_create, name="ai_practice_create"),
    path("practice/list/", views.ai_practice_list, name="ai_practice_list"),
    path("practice/<int:pk>/preview/", views.ai_practice_preview, name="ai_practice_preview"),
    path("practice/<int:pk>/take/", views.ai_practice_take, name="ai_practice_take"),
    path("practice/<int:pk>/submit/", views.ai_practice_submit, name="ai_practice_submit"),
    path("practice/<int:pk>/result/", views.ai_practice_result, name="ai_practice_result"),
    path("wrong-book/", views.ai_wrong_book, name="ai_wrong_book"),
]