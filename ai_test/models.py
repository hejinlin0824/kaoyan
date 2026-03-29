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
    explanation = models.TextField(null=True, blank=True, verbose_name="简要解析", help_text="AI 生成的解题思路与简要解析")

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
        ("pending", "生成中"),
        ("completed", "待练习"),
        ("taking", "作答中"),
        ("submitted", "已提交"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    subject = models.ForeignKey("kaoyan_app.Subject", on_delete=models.CASCADE, verbose_name="专业课")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    task_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="异步任务ID")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="生成完成时间")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始作答时间")
    duration_seconds = models.IntegerField(default=0, verbose_name="作答时长(秒)")
    score = models.IntegerField(default=0, verbose_name="客观题得分")
    total_objective_score = models.IntegerField(default=0, verbose_name="客观题总分")

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

    def delete(self, *args, **kwargs):
        # 级联删除该试卷关联的所有 AI 生成的题目
        question_ids = self.questions.values_list('question_id', flat=True)
        AIGeneratedQuestion.objects.filter(id__in=question_ids).delete()
        super().delete(*args, **kwargs)

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


class AIPracticeExam(models.Model):
    """AI题库组卷：从已有AI题库中不放回抽题，同步生成试卷"""
    STATUS_CHOICES = [
        ("preview", "预览中"),
        ("taking", "作答中"),
        ("submitted", "已提交"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="preview", verbose_name="状态")
    duration_seconds = models.IntegerField(default=0, verbose_name="作答时长(秒)")
    score = models.IntegerField(default=0, verbose_name="客观题得分")
    total_objective_score = models.IntegerField(default=0, verbose_name="客观题总分")

    # 组卷配置快照
    choice_count = models.IntegerField(default=0, verbose_name="选择题数量")
    fill_count = models.IntegerField(default=0, verbose_name="填空题数量")
    judge_count = models.IntegerField(default=0, verbose_name="判断题数量")
    short_count = models.IntegerField(default=0, verbose_name="简答题数量")
    calc_count = models.IntegerField(default=0, verbose_name="计算题数量")
    draw_count = models.IntegerField(default=0, verbose_name="画图题数量")

    class Meta:
        verbose_name = "AI题库练习卷"
        verbose_name_plural = "AI题库练习卷"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}的AI练习卷-{self.created_at.strftime('%m%d%H%M')}"


class AIPracticeExamQuestion(models.Model):
    """AI题库练习卷与AI题目的关联序列表"""
    exam = models.ForeignKey(AIPracticeExam, on_delete=models.CASCADE, related_name="questions", verbose_name="AI练习卷")
    question = models.ForeignKey(AIGeneratedQuestion, on_delete=models.CASCADE, verbose_name="AI题目")
    order = models.IntegerField(verbose_name="题目顺序")
    user_answer = models.TextField(null=True, blank=True, verbose_name="用户答案")
    is_correct = models.BooleanField(null=True, blank=True, verbose_name="是否正确")
    score = models.IntegerField(default=0, verbose_name="得分")

    class Meta:
        verbose_name = "AI练习卷题目明细"
        verbose_name_plural = "AI练习卷题目明细"
        ordering = ["order"]
        unique_together = ("exam", "question")

    def get_score_value(self):
        """该题满分值"""
        type_name = self.question.question_type.name
        if type_name == "选择":
            return 5
        elif type_name == "填空":
            return 5
        elif type_name == "判断":
            return 3
        return 0

    def __str__(self):
        return f"{self.exam} - 第{self.order}题"


class AIWrongQuestion(models.Model):
    """AI题错题本：记录用户在AI题库练习中的错题"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    question = models.ForeignKey(AIGeneratedQuestion, on_delete=models.CASCADE, verbose_name="AI题目")
    error_count = models.IntegerField(default=1, verbose_name="错误次数")
    last_wrong_at = models.DateTimeField(auto_now=True, verbose_name="最近错误时间")

    class Meta:
        verbose_name = "AI错题"
        verbose_name_plural = "AI错题本"
        unique_together = ("user", "question")
        ordering = ["-last_wrong_at"]

    def __str__(self):
        return f"{self.user.username}-AI错{self.error_count}次-{self.question.knowledge_point}"
