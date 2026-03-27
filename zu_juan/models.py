from django.db import models
from django.conf import settings


class Exam(models.Model):
    """试卷"""
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
        verbose_name = "试卷"
        verbose_name_plural = "试卷"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}的试卷-{self.created_at.strftime('%m%d%H%M')}"


class ExamQuestion(models.Model):
    """试卷题目"""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions", verbose_name="试卷")
    question = models.ForeignKey("kaoyan_app.Question", on_delete=models.CASCADE, verbose_name="题目")
    order = models.IntegerField(verbose_name="题目顺序")
    user_answer = models.TextField(null=True, blank=True, verbose_name="用户答案")
    is_correct = models.BooleanField(null=True, blank=True, verbose_name="是否正确")
    score = models.IntegerField(default=0, verbose_name="得分")

    class Meta:
        verbose_name = "试卷题目"
        verbose_name_plural = "试卷题目"
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


class WrongQuestion(models.Model):
    """错题本"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    question = models.ForeignKey("kaoyan_app.Question", on_delete=models.CASCADE, verbose_name="题目")
    error_count = models.IntegerField(default=1, verbose_name="错误次数")
    last_wrong_at = models.DateTimeField(auto_now=True, verbose_name="最近错误时间")

    class Meta:
        verbose_name = "错题"
        verbose_name_plural = "错题本"
        unique_together = ("user", "question")
        ordering = ["-last_wrong_at"]

    def __str__(self):
        return f"{self.user.username}-错{self.error_count}次-{self.question.knowledge_point}"