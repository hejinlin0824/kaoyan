from django.urls import path

from . import views

app_name = "ai_test"

urlpatterns = [
    # AI 智能组卷配置与生成入口
    path("create/", views.ai_exam_create, name="ai_exam_create"),
    
    # 用户的 AI 试卷列表（用于查看进度状态和历史记录）
    path("list/", views.ai_exam_list, name="ai_exam_list"),
    
    # 异步任务状态轮询接口 (供前端 AJAX 调用，返回 JSON)
    path("status/<int:pk>/", views.ai_exam_status, name="ai_exam_status"),
    
    # AI 试卷作答/练习页面 (无打分逻辑，纯净练习模式)
    path("take/<int:pk>/", views.ai_exam_take, name="ai_exam_take"),
]