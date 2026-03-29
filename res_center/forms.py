from django import forms
from .models import Resource


class ResourceForm(forms.ModelForm):
    """管理员上传资源表单"""
    class Meta:
        model = Resource
        fields = ["title", "category", "subject", "school", "cover",
                  "description", "link", "price"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8, "placeholder": "支持 Markdown + LaTeX 公式"}),
            "link": forms.URLInput(attrs={"placeholder": "https://..."}),
        }


class ResourceSubmissionForm(forms.Form):
    """用户投稿资源表单"""
    title = forms.CharField(max_length=200, label="标题",
                            widget=forms.TextInput(attrs={"placeholder": "资源标题"}))
    category = forms.IntegerField(label="分类",
                                  widget=forms.Select(attrs={}))
    subject = forms.IntegerField(required=False, label="关联专业课",
                                 widget=forms.Select(attrs={}))
    school = forms.IntegerField(required=False, label="关联学校",
                                widget=forms.Select(attrs={}))
    cover = forms.ImageField(required=False, label="封面图片")
    description = forms.CharField(label="简介",
                                  widget=forms.Textarea(attrs={"rows": 8, "placeholder": "支持 Markdown + LaTeX 公式，详细描述资源内容"}))
    link = forms.URLField(label="资源链接",
                          widget=forms.URLInput(attrs={"placeholder": "https://..."}))
    price = forms.IntegerField(initial=0, min_value=0, label="价格（点数）",
                               widget=forms.NumberInput(attrs={"min": 0, "placeholder": "0 表示免费"}))