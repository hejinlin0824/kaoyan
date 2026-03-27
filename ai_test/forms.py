from django import forms

from kaoyan_app.models import QuestionType, School, Subject
from .models import AIGeneratedQuestion

# 设置各题型允许的生成数量上限与提示说明
LIMITS = {
    "choice": (0, 10, "选择题"),
    "fill": (0, 10, "填空题"),
    "judge": (0, 10, "判断题"),
    "short": (0, 10, "简答题"),
    "calc": (0, 5, "计算题"),
    "draw": (0, 2, "画图题"),
}

class AIExamCreateForm(forms.Form):
    """AI智能组卷配置表单：用于接收各题型的生成数量请求"""
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        required=True,
        empty_label="请选择专业课",
        widget=forms.Select(attrs={"class": "form-input"}),
        label="专业课",
    )
    
    choice_count = forms.IntegerField(
        min_value=0, max_value=10, initial=5,
        label="选择题", 
        widget=forms.NumberInput(attrs={
            "class": "form-input", "min": 0, "max": 10
        })
    )
    
    fill_count = forms.IntegerField(
        min_value=0, max_value=10, initial=3,
        label="填空题", 
        widget=forms.NumberInput(attrs={
            "class": "form-input", "min": 0, "max": 10
        })
    )
    
    judge_count = forms.IntegerField(
        min_value=0, max_value=10, initial=3,
        label="判断题", 
        widget=forms.NumberInput(attrs={
            "class": "form-input", "min": 0, "max": 10
        })
    )
    
    short_count = forms.IntegerField(
        min_value=0, max_value=10, initial=2,
        label="简答题", 
        widget=forms.NumberInput(attrs={
            "class": "form-input", "min": 0, "max": 10
        })
    )
    
    calc_count = forms.IntegerField(
        min_value=0, max_value=5, initial=1,
        label="计算题", 
        widget=forms.NumberInput(attrs={
            "class": "form-input", "min": 0, "max": 5
        })
    )
    
    draw_count = forms.IntegerField(
        min_value=0, max_value=2, initial=0,
        label="画图题", 
        widget=forms.NumberInput(attrs={
            "class": "form-input", "min": 0, "max": 2
        })
    )

    def clean(self):
        """
        全局表单清洗与逻辑校验：
        1. 确保用户至少选择了一道题
        2. 防止题目总数越界
        """
        cleaned = super().clean()
        
        # 汇总所有题型数量
        total = sum(cleaned.get(f"{k}_count", 0) for k in LIMITS)
        
        if total == 0:
            raise forms.ValidationError("至少选择 1 道题目交由 AI 生成。")
            
        if total > 47:
            raise forms.ValidationError(f"题目总数不能超过 47 道，当前共申请生成 {total} 道。")
            
        return cleaned


class AIQuestionSearchForm(forms.Form):
    """AI 题库查询表单"""
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
        choices=[("", "全部难度")] + AIGeneratedQuestion.DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-input"}),
    )


class AIPracticeExamCreateForm(forms.Form):
    """AI题库组卷表单：从已有AI题库中抽题，不需要选科目（题目本身带分类）"""
    choice_count = forms.IntegerField(
        min_value=0, max_value=10, initial=5,
        label="选择题",
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 10})
    )
    fill_count = forms.IntegerField(
        min_value=0, max_value=10, initial=3,
        label="填空题",
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 10})
    )
    judge_count = forms.IntegerField(
        min_value=0, max_value=10, initial=3,
        label="判断题",
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 10})
    )
    short_count = forms.IntegerField(
        min_value=0, max_value=10, initial=2,
        label="简答题",
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 10})
    )
    calc_count = forms.IntegerField(
        min_value=0, max_value=5, initial=1,
        label="计算题",
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 5})
    )
    draw_count = forms.IntegerField(
        min_value=0, max_value=2, initial=0,
        label="画图题",
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 2})
    )

    def clean(self):
        cleaned = super().clean()
        total = sum(cleaned.get(f"{k}_count", 0) for k in LIMITS)
        if total == 0:
            raise forms.ValidationError("至少选择 1 道题目。")
        if total > 47:
            raise forms.ValidationError(f"题目总数不能超过 47 道，当前共 {total} 道。")
        return cleaned
