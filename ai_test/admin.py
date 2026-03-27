from django.contrib import admin
from .models import (
    AIGeneratedQuestion, AIExam, AIExamQuestion,
    AIPracticeExam, AIPracticeExamQuestion, AIWrongQuestion,
)

@admin.register(AIGeneratedQuestion)
class AIGeneratedQuestionAdmin(admin.ModelAdmin):
    """AI生成的练习题后台管理"""
    list_display = ("id", "year", "school", "question_type", "difficulty", "knowledge_point", "created_at")
    list_filter = ("year", "school", "question_type", "difficulty")
    search_fields = ("knowledge_point", "content")
    readonly_fields = ("created_at",)
    # 使用 raw_id_fields 避免数据量大时下拉框加载卡顿
    raw_id_fields = ("original_question", "school", "question_type")

    fieldsets = (
        ("溯源与分类", {
            "fields": ("original_question", "year", "school", "question_type", "difficulty", "knowledge_point")
        }),
        ("AI 生成内容", {
            "fields": ("content", "options")
        }),
        ("时间信息", {
            "fields": ("created_at",)
        }),
    )


class AIExamQuestionInline(admin.TabularInline):
    """在 AI 试卷详情页内联展示关联的 AI 题目"""
    model = AIExamQuestion
    extra = 0
    raw_id_fields = ("question",)
    readonly_fields = ("order", "user_answer")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # 禁止在后台手动为试卷添加题目，必须由 AI 异步任务生成
        return False


@admin.register(AIExam)
class AIExamAdmin(admin.ModelAdmin):
    """AI 智能试卷后台管理"""
    list_display = ("id", "user", "status", "get_total_questions", "created_at", "completed_at", "task_id")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "task_id")
    readonly_fields = ("created_at", "completed_at")
    raw_id_fields = ("user",)
    inlines = [AIExamQuestionInline]

    fieldsets = (
        ("任务状态", {
            "fields": ("user", "status", "task_id", "created_at", "completed_at")
        }),
        ("抽题配置快照", {
            "fields": ("choice_count", "fill_count", "judge_count", "short_count", "calc_count", "draw_count")
        }),
    )

    @admin.display(description="题目总数")
    def get_total_questions(self, obj):
        return (obj.choice_count + obj.fill_count + obj.judge_count + 
                obj.short_count + obj.calc_count + obj.draw_count)


@admin.register(AIExamQuestion)
class AIExamQuestionAdmin(admin.ModelAdmin):
    """AI 试卷题目明细独立后台管理（备用查询）"""
    list_display = ("id", "exam", "question", "order")
    search_fields = ("exam__id", "question__content")
    raw_id_fields = ("exam", "question")
    list_filter = ("exam__status",)


# ─── AI题库组卷 Admin ───

class AIPracticeExamQuestionInline(admin.TabularInline):
    """AI练习卷内联题目"""
    model = AIPracticeExamQuestion
    extra = 0
    raw_id_fields = ("question",)
    readonly_fields = ("order", "user_answer", "is_correct", "score")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AIPracticeExam)
class AIPracticeExamAdmin(admin.ModelAdmin):
    """AI题库练习卷后台管理"""
    list_display = ("id", "user", "status", "score", "total_objective_score", "created_at", "duration_seconds")
    list_filter = ("status", "created_at")
    search_fields = ("user__username",)
    readonly_fields = ("created_at", "score", "total_objective_score", "duration_seconds")
    raw_id_fields = ("user",)
    inlines = [AIPracticeExamQuestionInline]

    fieldsets = (
        ("基本信息", {
            "fields": ("user", "status", "created_at")
        }),
        ("成绩信息", {
            "fields": ("score", "total_objective_score", "duration_seconds")
        }),
        ("组卷配置快照", {
            "fields": ("choice_count", "fill_count", "judge_count", "short_count", "calc_count", "draw_count")
        }),
    )


@admin.register(AIPracticeExamQuestion)
class AIPracticeExamQuestionAdmin(admin.ModelAdmin):
    """AI练习卷题目明细后台管理"""
    list_display = ("id", "exam", "question", "order", "is_correct", "score")
    search_fields = ("exam__id", "question__content")
    raw_id_fields = ("exam", "question")
    list_filter = ("exam__status",)


@admin.register(AIWrongQuestion)
class AIWrongQuestionAdmin(admin.ModelAdmin):
    """AI错题本后台管理"""
    list_display = ("id", "user", "question", "error_count", "last_wrong_at")
    list_filter = ("last_wrong_at",)
    search_fields = ("user__username", "question__knowledge_point", "question__content")
    raw_id_fields = ("user", "question")
