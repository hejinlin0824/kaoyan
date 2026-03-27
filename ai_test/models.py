from django.db import models
from django.conf import settings

class AIGeneratedQuestion(models.Model):
    """AI生成的练习题（完全独立，不含答案、插图，不污染原题库）"""
    DIFFICULTY_CHOICES = [
        ("易", "易"),
        ("中", "中"),
        ("难", "难"),
    ]

    # 溯源：记录是由哪道原题变式而来的，使用 SET_NULL 保证原题删除时生成的题不丢失
    original_question = models.ForeignKey(
        "kaoyan_app.Question",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="溯源真题"
    )

    year = models.IntegerField(verbose_name="参考年份")
    school = models.ForeignKey("kaoyan_app.School", on_delete=models.CASCADE, verbose_name="参考学校")
    question_type = models.ForeignKey("kaoyan_app.QuestionType", on_delete=models.CASCADE, verbose_name="题型")
    difficulty = models.CharField(max_length=2, choices=DIFFICULTY_CHOICES, verbose_name="难度")
    knowledge_point = models.CharField(max_length=200, verbose_name="知识点")

    content = models.TextField(verbose_name="AI改写题干", help_text="支持 Markdown + LaTeX 公式")
    options = models.JSONField(
        null=True, blank=True, verbose_name="选项",
        help_text='选择题必填，JSON 对象格式，如 {"A": "内容", "B": "内容"}'
    )
    correct_answer = models.TextField(null=True, blank=True, verbose_name="正确答案", help_text="选择题填A/B/C/D，判断题填对/错，填空题填标准答案，主观题留空")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="生成时间")

    class Meta:
        verbose_name = "AI练习题"
        verbose_name_plural = "AI练习题"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AI变式-{self.question_type.name}-{self.knowledge_point}"


class AIExam(models.Model):
    """AI组卷生成的异步试卷记录"""
    STATUS_CHOICES = [
        ("pending", "进行中"),
        ("completed", "已完成"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="生成状态")
    task_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="异步任务ID")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    # 用户提交的组卷需求快照，交由异步任务执行抽题改写
    choice_count = models.IntegerField(default=0, verbose_name="选择题数量")
    fill_count = models.IntegerField(default=0, verbose_name="填空题数量")
    judge_count = models.IntegerField(default=0, verbose_name="判断题数量")
    short_count = models.IntegerField(default=0, verbose_name="简答题数量")
    calc_count = models.IntegerField(default=0, verbose_name="计算题数量")
    draw_count = models.IntegerField(default=0, verbose_name="画图题数量")

    class Meta:
        verbose_name = "AI智能试卷"
        verbose_name_plural = "AI智能试卷"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}的AI试卷-{self.created_at.strftime('%m%d%H%M')}"


class AIExamQuestion(models.Model):
    """AI试卷与AI题目的关联序列表"""
    exam = models.ForeignKey(AIExam, on_delete=models.CASCADE, related_name="questions", verbose_name="AI试卷")
    question = models.ForeignKey(AIGeneratedQuestion, on_delete=models.CASCADE, verbose_name="AI题目")
    order = models.IntegerField(verbose_name="题目顺序")
    user_answer = models.TextField(null=True, blank=True, verbose_name="用户答题记录")

    class Meta:
        verbose_name = "AI试卷题目明细"
        verbose_name_plural = "AI试卷题目明细"
        ordering = ["order"]
        unique_together = ("exam", "question")

    def __str__(self):
        return f"{self.exam} - 第{self.order}题"