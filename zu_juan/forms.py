from django import forms

LIMITS = {
    "choice": (0, 10, "选择题"),
    "fill": (0, 10, "填空题"),
    "judge": (0, 10, "判断题"),
    "short": (0, 10, "简答题"),
    "calc": (0, 5, "计算题"),
    "draw": (0, 2, "画图题"),
}


class ExamCreateForm(forms.Form):
    """组卷表单"""
    choice_count = forms.IntegerField(min_value=0, max_value=10, initial=5,
                                     label="选择题", widget=forms.NumberInput(attrs={
                                         "class": "form-input", "min": 0, "max": 10}))
    fill_count = forms.IntegerField(min_value=0, max_value=10, initial=3,
                                    label="填空题", widget=forms.NumberInput(attrs={
                                        "class": "form-input", "min": 0, "max": 10}))
    judge_count = forms.IntegerField(min_value=0, max_value=10, initial=3,
                                     label="判断题", widget=forms.NumberInput(attrs={
                                         "class": "form-input", "min": 0, "max": 10}))
    short_count = forms.IntegerField(min_value=0, max_value=10, initial=2,
                                     label="简答题", widget=forms.NumberInput(attrs={
                                         "class": "form-input", "min": 0, "max": 10}))
    calc_count = forms.IntegerField(min_value=0, max_value=5, initial=1,
                                    label="计算题", widget=forms.NumberInput(attrs={
                                        "class": "form-input", "min": 0, "max": 5}))
    draw_count = forms.IntegerField(min_value=0, max_value=2, initial=0,
                                    label="画图题", widget=forms.NumberInput(attrs={
                                        "class": "form-input", "min": 0, "max": 2}))

    def clean(self):
        cleaned = super().clean()
        total = sum(cleaned.get(f"{k}_count", 0) for k in LIMITS)
        if total == 0:
            raise forms.ValidationError("至少选择 1 道题目")
        if total > 47:
            raise forms.ValidationError(f"题目总数不能超过 47 道，当前 {total} 道")
        return cleaned