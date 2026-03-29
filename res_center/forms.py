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