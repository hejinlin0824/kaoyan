import re

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User

# 允许注册的邮箱域名白名单
ALLOWED_EMAIL_DOMAINS = [
    "qq.com",
    "163.com",
    "126.com",
    "gmail.com",
]


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="邮箱",
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "支持 QQ / 网易 / Gmail 邮箱"}),
    )
    username = forms.CharField(
        label="用户名",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "仅限英文、数字、下划线"}),
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

    def clean_username(self):
        username = self.cleaned_data.get("username")
        # 禁止中文
        if re.search(r'[\u4e00-\u9fff]', username):
            raise forms.ValidationError("用户名不允许包含中文字符，请使用英文、数字或下划线")
        # 仅允许字母、数字、下划线，长度 3-20
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            raise forms.ValidationError("用户名仅支持 3-20 位英文、数字、下划线")
        # 防止重复（Django UserCreationForm 会检查，但自定义模型需手动确认）
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("该用户名已被注册，请换一个")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        # 检查邮箱域名白名单
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if domain not in ALLOWED_EMAIL_DOMAINS:
            allowed = "、".join(ALLOWED_EMAIL_DOMAINS)
            raise forms.ValidationError(f"仅支持以下邮箱：{allowed}")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("该邮箱已被注册")
        return email


class LoginForm(forms.Form):
    username = forms.CharField(
        label="用户名或邮箱",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "用户名 / 邮箱"}),
    )
    password = forms.CharField(
        label="密码",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "请输入密码"}),
    )

    def clean_username(self):
        """统一返回：如果是邮箱则查找对应 username"""
        raw = self.cleaned_data.get("username", "").strip()
        if "@" in raw:
            try:
                user = User.objects.get(email__iexact=raw)
                return user.username
            except User.DoesNotExist:
                raise forms.ValidationError("该邮箱未注册")
        return raw


class PasswordResetRequestForm(forms.Form):
    """密码重置 - 第一步：输入邮箱"""
    email = forms.EmailField(
        label="邮箱",
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "请输入注册时使用的邮箱"}),
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError("该邮箱未注册或账号未激活")
        return email


class ProfileEditForm(forms.ModelForm):
    """个人资料编辑"""
    bio = forms.CharField(
        label="个人简介",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "placeholder": "写点什么介绍一下自己吧（最多300字）",
            "rows": 4,
            "maxlength": "300",
        }),
    )
    avatar = forms.ImageField(
        label="更换头像",
        required=False,
        widget=forms.FileInput(attrs={
            "class": "form-input",
            "accept": "image/*",
        }),
    )
    target_school = forms.ModelChoiceField(
        label="目标院校",
        required=False,
        queryset=None,
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    kaoyan_session = forms.ChoiceField(
        label="考研届次",
        required=False,
        choices=[("", "-- 请选择 --")] + User.KAOYAN_SESSION_CHOICES,
        widget=forms.Select(attrs={"class": "form-input"}),
    )
    study_start_date = forms.DateField(
        label="学习开始日期",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )

    class Meta:
        model = User
        fields = ("avatar", "bio", "target_school", "kaoyan_session", "study_start_date")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from kaoyan_app.models import School
        self.fields["target_school"].queryset = School.objects.all()
        self.fields["target_school"].empty_label = "-- 请选择 --"

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "content_type"):
            # 限制 2MB
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError("头像文件不能超过 2MB")
            # 限制格式
            allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
            if avatar.content_type not in allowed_types:
                raise forms.ValidationError("仅支持 JPG、PNG、GIF、WebP 格式")
        return avatar


class PasswordResetConfirmForm(forms.Form):
    """密码重置 - 第二步：设置新密码"""
    new_password = forms.CharField(
        label="新密码",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "请输入新密码"}),
    )
    confirm_password = forms.CharField(
        label="确认新密码",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "请再次输入新密码"}),
    )

    def clean_confirm_password(self):
        pwd1 = self.cleaned_data.get("new_password")
        pwd2 = self.cleaned_data.get("confirm_password")
        if pwd1 and pwd2 and pwd1 != pwd2:
            raise forms.ValidationError("两次输入的密码不一致")
        return pwd2
