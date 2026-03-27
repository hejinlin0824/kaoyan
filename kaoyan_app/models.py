from django.db import models


class School(models.Model):
    """学校"""
    name = models.CharField(max_length=100, unique=True, verbose_name="学校名称")

    class Meta:
        verbose_name = "学校"
        verbose_name_plural = "学校"
        ordering = ["name"]

    def __str__(self):
        return self.name


class QuestionType(models.Model):
    """题型"""
    name = models.CharField(max_length=50, unique=True, verbose_name="题型名称")

    class Meta:
        verbose_name = "题型"
        verbose_name_plural = "题型"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Question(models.Model):
    """题目"""
    DIFFICULTY_CHOICES = [
        ("易", "易"),
        ("中", "中"),
        ("难", "难"),
    ]

    year = models.IntegerField(verbose_name="年份")
    school = models.ForeignKey(School, on_delete=models.CASCADE, verbose_name="学校")
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE, verbose_name="题型")
    difficulty = models.CharField(max_length=2, choices=DIFFICULTY_CHOICES, verbose_name="难度")
    knowledge_point = models.CharField(max_length=200, verbose_name="知识点")
    content = models.TextField(verbose_name="题干", help_text="支持 Markdown + LaTeX 公式（$...$ / $$...$$）")
    options = models.JSONField(
        null=True, blank=True, verbose_name="选项",
        help_text='选择题必填，JSON 对象格式，如 {"A": "内容", "B": "内容"}'
    )
    correct_answer = models.TextField(null=True, blank=True, verbose_name="正确答案", help_text="选择题填 A/B/C/D，判断题填 对/错，填空题多个空用分号隔开，解答题填参考答案要点，绘图题可留空")
    answer = models.TextField(verbose_name="答案解析", help_text="支持 Markdown + LaTeX 公式，填空/简答等非选择题填写具体答案")
    image = models.ImageField(upload_to="questions/%Y/%m/", null=True, blank=True, verbose_name="插图")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "题目"
        verbose_name_plural = "题目"
        ordering = ["-year", "school", "question_type"]

    def __str__(self):
        return f"{self.year}-{self.school.name}-{self.question_type.name}-{self.knowledge_point}"

    def to_dict(self):
        """序列化为字典，用于 JSON 备份"""
        return {
            "id": self.id,
            "year": self.year,
            "school": self.school.name,
            "question_type": self.question_type.name,
            "difficulty": self.difficulty,
            "knowledge_point": self.knowledge_point,
            "content": self.content,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "answer": self.answer,
            "image": self.image.url if self.image else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }