from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="邮箱",
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "请输入邮箱"}),
    )
    username = forms.CharField(
        label="用户名",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "请输入用户名"}),
    )
    password1 = forms.CharField(
        label="密码",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "请输入密码"}),
    )
    password2 = forms.CharField(
        label="确认密码",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "请再次输入密码"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("该邮箱已被注册")
        return email


class LoginForm(forms.Form):
    username = forms.CharField(
        label="用户名",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "请输入用户名"}),
    )
    password = forms.CharField(
        label="密码",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "请输入密码"}),
    )
