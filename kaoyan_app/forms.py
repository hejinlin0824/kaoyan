from django import forms

from .models import Question, QuestionType, School, Subject


class QuestionForm(forms.ModelForm):
    """题目录入表单"""
    # 四个独立选项输入框，不对应模型字段，仅用于表单收集
    option_a = forms.CharField(required=False, label="选项 A", widget=forms.TextInput(attrs={
        "class": "form-input", "placeholder": "A. ",
    }))
    option_b = forms.CharField(required=False, label="选项 B", widget=forms.TextInput(attrs={
        "class": "form-input", "placeholder": "B. ",
    }))
    option_c = forms.CharField(required=False, label="选项 C", widget=forms.TextInput(attrs={
        "class": "form-input", "placeholder": "C. ",
    }))
    option_d = forms.CharField(required=False, label="选项 D", widget=forms.TextInput(attrs={
        "class": "form-input", "placeholder": "D. ",
    }))
    correct_answer = forms.CharField(required=False, label="正确答案", widget=forms.Textarea(attrs={
        "class": "form-input",
        "rows": 2,
        "placeholder": "选择题: A/B/C/D\n判断题: 对/错\n填空题: 答案1;答案2;答案3\n解答题: 参考答案要点\n绘图题: 可留空",
        "id": "id_correct_answer",
    }))

    class Meta:
        model = Question
        fields = ["subject", "year", "school", "question_type", "difficulty", "knowledge_point", "content", "correct_answer", "answer", "image"]
        widgets = {
            "subject": forms.Select(attrs={"class": "form-input"}),
            "year": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "例如：2025",
                "min": "1990", "max": "2099",
            }),
            "school": forms.Select(attrs={"class": "form-input"}),
            "question_type": forms.Select(attrs={"class": "form-input", "id": "id_question_type"}),
            "difficulty": forms.Select(attrs={"class": "form-input"}),
            "knowledge_point": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "例如：数据结构-二叉树",
            }),
            "content": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 8,
                "placeholder": "支持 Markdown 和 LaTeX 公式\n行内公式: $E=mc^2$\n块级公式: $$\n\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}\n$$",
                "id": "id_content",
            }),
            "answer": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 6,
                "placeholder": "支持 Markdown 和 LaTeX 公式",
                "id": "id_answer",
            }),
            "image": forms.FileInput(attrs={
                "class": "form-input",
                "accept": "image/*",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 学校默认选中新疆大学
        default_school = School.objects.filter(name="新疆大学").first()
        if default_school and not self.initial.get("school"):
            self.initial["school"] = default_school.id

    def clean_year(self):
        year = self.cleaned_data["year"]
        if year < 1990 or year > 2099:
            raise forms.ValidationError("年份应在 1990-2099 之间")
        return year

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.options = self.cleaned_data.get("options")
        instance.correct_answer = self.cleaned_data.get("correct_answer") or None
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned = super().clean()
        question_type = cleaned.get("question_type")
        type_name = question_type.name if question_type else ""

        if type_name == "选择":
            # 将四个选项合并为字典
            opts = {}
            for letter in ["a", "b", "c", "d"]:
                val = cleaned.get(f"option_{letter}", "")
                if val and val.strip():
                    opts[letter.upper()] = val.strip()
            if len(opts) < 2:
                self.add_error("option_a", "选择题至少需要填写 2 个选项")
            cleaned["options"] = opts if opts else None
            # 校验正确选项是否在已填选项中
            correct = (cleaned.get("correct_answer") or "").strip().upper()
            if correct and correct not in opts:
                self.add_error("correct_answer", f"正确选项 {correct} 没有填写对应内容")
        else:
            cleaned["options"] = None

        # 清理临时字段
        for letter in ["a", "b", "c", "d"]:
            cleaned.pop(f"option_{letter}", None)
        return cleaned


class QuestionSearchForm(forms.Form):
    """题目查询表单"""
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        empty_label="全部专业课",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    year = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={
        "class": "form-input", "placeholder": "年份",
    }))
    school = forms.ModelChoiceField(
        queryset=School.objects.all(),
        required=False,
        empty_label="全部学校",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    question_type = forms.ModelChoiceField(
        queryset=QuestionType.objects.all(),
        required=False,
        empty_label="全部题型",
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    difficulty = forms.ChoiceField(
        choices=[("", "全部难度")] + Question.DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-input"}),
    )