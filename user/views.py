from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm


def home(request):
    user = request.user
    is_vip = user.is_vip() if user.is_authenticated else False
    vip_label = dict(user.VIP_CHOICES).get(user.vip_level, "") if user.is_authenticated else ""
    return render(request, "user/home.html", {
        "user": user,
        "is_vip": is_vip,
        "vip_label": vip_label,
    })


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("user:login")
    else:
        form = RegisterForm()
    return render(request, "user/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("user:home")
            else:
                form.add_error(None, "用户名或密码错误")
    else:
        form = LoginForm()
    return render(request, "user/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("user:home")


def vip_page(request):
    """VIP 开通页面"""
    from django.templatetags.static import static
    return render(request, "user/vip.html", {
        "wechat_qrcode_url": static("images/wechat_qrcode.png"),
    })
