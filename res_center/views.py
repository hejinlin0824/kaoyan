from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from user.coin_utils import add_coins
from .forms import ResourceForm
from .models import Resource, ResourceCategory, ResourcePurchase


def resource_list(request):
    """资源中心列表页 - 所有人可看"""
    resources = Resource.objects.select_related("category", "school", "subject").all()

    # 筛选
    category_id = request.GET.get("category")
    school_id = request.GET.get("school")
    subject_id = request.GET.get("subject")
    q = request.GET.get("q", "").strip()

    if category_id:
        resources = resources.filter(category_id=category_id)
    if school_id:
        resources = resources.filter(school_id=school_id)
    if subject_id:
        resources = resources.filter(subject_id=subject_id)
    if q:
        resources = resources.filter(title__icontains=q)

    categories = ResourceCategory.objects.all()
    from kaoyan_app.models import School, Subject
    schools = School.objects.all()
    subjects = Subject.objects.all()

    # 用户已购买的资源ID集合
    purchased_ids = set()
    if request.user.is_authenticated:
        purchased_ids = set(
            ResourcePurchase.objects.filter(user=request.user)
            .values_list("resource_id", flat=True)
        )

    paginator = Paginator(resources, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # 保留筛选参数
    search_params = request.GET.copy()
    search_params.pop("page", None)
    search_str = search_params.urlencode()

    is_vip = request.user.is_authenticated and request.user.is_vip()

    return render(request, "res_center/resource_list.html", {
        "page_obj": page_obj,
        "categories": categories,
        "schools": schools,
        "subjects": subjects,
        "purchased_ids": purchased_ids,
        "search_str": search_str,
        "is_vip": is_vip,
        # 当前筛选值
        "current_category": category_id,
        "current_school": school_id,
        "current_subject": subject_id,
        "current_q": q,
    })


def resource_detail(request, pk):
    """资源详情页"""
    resource = get_object_or_404(Resource.objects.select_related(
        "category", "school", "subject", "uploaded_by"), pk=pk)

    # 是否已购买
    purchased = False
    if request.user.is_authenticated:
        purchased = ResourcePurchase.objects.filter(
            user=request.user, resource=resource
        ).exists()

    is_vip = request.user.is_authenticated and request.user.is_vip()

    return render(request, "res_center/resource_detail.html", {
        "resource": resource,
        "purchased": purchased,
        "is_vip": is_vip,
        "can_access": purchased or is_vip or resource.price == 0,
    })


@login_required
def resource_purchase(request, pk):
    """购买资源（点数支付）"""
    if request.method != "POST":
        return redirect("res_center:detail", pk)

    resource = get_object_or_404(Resource, pk=pk)
    user = request.user

    # VIP 免费
    if user.is_vip():
        ResourcePurchase.objects.get_or_create(
            user=user, resource=resource,
            defaults={"coins_paid": 0}
        )
        Resource.objects.filter(pk=resource.pk).update(
            download_count=F("download_count") + 1
        )
        return redirect("res_center:detail", pk)

    # 免费资源
    if resource.price == 0:
        ResourcePurchase.objects.get_or_create(
            user=user, resource=resource,
            defaults={"coins_paid": 0}
        )
        Resource.objects.filter(pk=resource.pk).update(
            download_count=F("download_count") + 1
        )
        return redirect("res_center:detail", pk)

    # 已购买
    if ResourcePurchase.objects.filter(user=user, resource=resource).exists():
        return redirect("res_center:detail", pk)

    # 扣点数
    success, msg = add_coins(
        user, -resource.price,
        reason="resource_purchase",
        description=f"购买资源: {resource.title}"
    )
    if not success:
        return render(request, "res_center/resource_detail.html", {
            "resource": resource,
            "purchased": False,
            "is_vip": False,
            "can_access": False,
            "error": msg or "点数不足，无法购买",
        })

    ResourcePurchase.objects.create(
        user=user, resource=resource, coins_paid=resource.price
    )
    Resource.objects.filter(pk=resource.pk).update(
        download_count=F("download_count") + 1
    )
    return redirect("res_center:detail", pk)


@staff_member_required(login_url="/login/")
def resource_upload(request):
    """管理员上传资源"""
    from kaoyan_app.models import School, Subject

    if request.method == "POST":
        form = ResourceForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.uploaded_by = request.user
            resource.save()
            return redirect("res_center:detail", resource.pk)
    else:
        form = ResourceForm()

    return render(request, "res_center/resource_upload.html", {
        "form": form,
        "categories": ResourceCategory.objects.all(),
        "schools": School.objects.all(),
        "subjects": Subject.objects.all(),
    })


@staff_member_required(login_url="/login/")
def resource_edit(request, pk):
    """管理员编辑资源"""
    from kaoyan_app.models import School, Subject

    resource = get_object_or_404(Resource, pk=pk)
    if request.method == "POST":
        form = ResourceForm(request.POST, request.FILES, instance=resource)
        if form.is_valid():
            form.save()
            return redirect("res_center:detail", resource.pk)
    else:
        form = ResourceForm(instance=resource)

    return render(request, "res_center/resource_upload.html", {
        "form": form,
        "resource": resource,
        "is_edit": True,
        "categories": ResourceCategory.objects.all(),
        "schools": School.objects.all(),
        "subjects": Subject.objects.all(),
    })


@login_required
def my_purchases(request):
    """我购买的资源"""
    purchases = ResourcePurchase.objects.filter(
        user=request.user
    ).select_related("resource__category", "resource__school", "resource__subject").order_by("-created_at")

    paginator = Paginator(purchases, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    is_vip = request.user.is_authenticated and request.user.is_vip()

    return render(request, "res_center/my_purchases.html", {
        "page_obj": page_obj,
        "is_vip": is_vip,
    })
