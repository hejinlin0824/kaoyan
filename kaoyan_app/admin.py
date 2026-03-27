from django.contrib import admin

from .models import Question, QuestionType, School, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(QuestionType)
class QuestionTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "year", "school", "question_type", "difficulty", "knowledge_point", "created_at")
    list_filter = ("subject", "year", "school", "question_type", "difficulty")
    search_fields = ("knowledge_point", "content", "answer")
    autocomplete_fields = ("school", "question_type", "subject")
    date_hierarchy = "created_at"

    fieldsets = (
        ("基本信息", {
            "fields": ("subject", "year", "school", "question_type", "difficulty", "knowledge_point"),
        }),
        ("题目内容", {
            "fields": ("content", "options", "correct_answer", "answer", "image"),
        }),
    )