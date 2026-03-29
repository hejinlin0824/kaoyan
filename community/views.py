import json
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_GET

from kaoyan_app.models import Question
from ai_test.models import AIGeneratedQuestion
from .models import Comment, CommentLike, Notification, QuestionReport


def _get_top_comment(comment):
    """递归找到顶级评论"""
    if comment.parent is None:
        return comment
    return _get_top_comment(comment.parent)


def _get_discuss_context(question_id, source, extra_context=None):
    """通用：获取讨论区上下文（支持多层嵌套回复）"""
    qs = Comment.objects.filter(question_id=question_id, question_source=source)

    # 获取所有顶级评论
    comments = list(qs.filter(parent__isnull=True).annotate(
        like_count=Count("likes", distinct=True),
        reply_count=Count("replies", distinct=True),
    ))
    comments.sort(key=lambda c: (c.like_count + c.reply_count, c.created_at), reverse=True)

    # 预加载所有回复（含嵌套回复）—— 按顶级评论分组
    all_replies = qs.filter(parent__isnull=False).annotate(like_count=Count("likes", distinct=True))
    # 找到所有回复的顶级评论归属
    reply_map = {}  # top_comment_id -> [replies]
    reply_obj_map = {r.id: r for r in all_replies}
    for r in all_replies:
        top = _get_top_comment(r)
        reply_map.setdefault(top.id, []).append(r)
    for c in comments:
        c.replies_list = sorted(
            reply_map.get(c.id, []),
            key=lambda r: r.created_at,
        )

    return {
        "comments": comments,
        "comment_count": qs.count(),
    }


def question_discuss(request, pk):
    """真题详情 + 讨论区"""
    question = get_object_or_404(Question, pk=pk)
    ctx = _get_discuss_context(pk, "kaoyan")

    liked_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(CommentLike.objects.filter(
            user=request.user, comment__question_id=pk, comment__question_source="kaoyan",
        ).values_list("comment_id", flat=True))

    is_vip = False
    if request.user.is_authenticated:
        is_vip = request.user.is_vip()

    return render(request, "community/question_discuss.html", {
        "question": question,
        "question_source": "kaoyan",
        "comments": ctx["comments"],
        "liked_ids": liked_ids,
        "comment_count": ctx["comment_count"],
        "is_vip": is_vip,
    })


def ai_question_discuss(request, pk):
    """AI题目详情 + 讨论区"""
    question = get_object_or_404(AIGeneratedQuestion, pk=pk)
    ctx = _get_discuss_context(pk, "ai")

    liked_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(CommentLike.objects.filter(
            user=request.user, comment__question_id=pk, comment__question_source="ai",
        ).values_list("comment_id", flat=True))

    is_vip = False
    if request.user.is_authenticated:
        is_vip = request.user.is_vip()

    return render(request, "community/ai_question_discuss.html", {
        "question": question,
        "question_source": "ai",
        "comments": ctx["comments"],
        "liked_ids": liked_ids,
        "comment_count": ctx["comment_count"],
        "is_vip": is_vip,
    })


@login_required
@require_POST
def add_comment(request, pk):
    """发布评论/回复（通用，支持 source=kaoyan/ai）"""
    source = request.POST.get("source", "kaoyan")
    content = request.POST.get("content", "").strip()
    parent_id = request.POST.get("parent_id")

    if not content:
        return JsonResponse({"ok": False, "msg": "评论内容不能为空"}, status=400)

    # 验证题目存在
    if source == "ai":
        get_object_or_404(AIGeneratedQuestion, pk=pk)
    else:
        get_object_or_404(Question, pk=pk)

    parent = None
    if parent_id:
        try:
            parent = Comment.objects.get(id=int(parent_id), question_id=pk, question_source=source)
        except (Comment.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"ok": False, "msg": "回复的评论不存在"}, status=400)

    comment = Comment.objects.create(
        user=request.user,
        question_id=pk,
        question_source=source,
        parent=parent,
        content=content,
    )

    # 构建讨论页 URL
    if source == "ai":
        discuss_url = f"/community/ai-question/{pk}/"
    else:
        discuss_url = f"/community/question/{pk}/"

    # 创建回复通知
    if parent and parent.user != request.user:
        Notification.objects.create(
            recipient=parent.user,
            sender=request.user,
            noti_type="reply",
            content=f"{request.user.username} 回复了你的评论：{content[:50]}",
            url=discuss_url,
        )

    return JsonResponse({
        "ok": True,
        "comment": {
            "id": comment.id,
            "username": comment.user.username,
            "avatar": comment.user.avatar.url,
            "content": comment.content,
            "time": comment.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_reply": comment.is_reply,
            "parent_username": parent.user.username if parent else None,
            "like_count": 0,
            "reply_count": 0,
        },
    })


@login_required
@require_POST
def toggle_like(request):
    """点赞/取消点赞"""
    data = json.loads(request.body)
    comment_id = data.get("comment_id")
    try:
        comment = Comment.objects.get(id=comment_id)
    except Comment.DoesNotExist:
        return JsonResponse({"ok": False, "msg": "评论不存在"}, status=404)

    like, created = CommentLike.objects.get_or_create(
        user=request.user, comment=comment,
    )
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        # 创建点赞通知（不通知自己）
        if comment.user != request.user:
            if comment.question_source == "ai":
                url = f"/community/ai-question/{comment.question_id}/"
            else:
                url = f"/community/question/{comment.question_id}/"
            Notification.objects.create(
                recipient=comment.user,
                sender=request.user,
                noti_type="like",
                content=f"{request.user.username} 赞了你的评论：{comment.content[:50]}",
                url=url,
            )

    return JsonResponse({
        "ok": True,
        "liked": liked,
        "like_count": comment.likes.count(),
    })


# ── 通知 ──

@login_required
def notification_list(request):
    """通知列表页"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related("sender")[:50]

    return render(request, "community/notification_list.html", {
        "notifications": notifications,
    })


@login_required
def notification_unread_count(request):
    """未读通知数量 API"""
    count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    return JsonResponse({"count": count})


@login_required
def notification_latest(request):
    """最新通知 API（下拉面板用）"""
    notes = Notification.objects.filter(
        recipient=request.user
    ).select_related("sender")[:8]

    data = []
    for n in notes:
        data.append({
            "id": n.id,
            "sender_name": n.sender.username,
            "sender_avatar": n.sender.avatar.url,
            "type": n.noti_type,
            "content": n.content,
            "url": n.url,
            "is_read": n.is_read,
            "time": n.created_at.strftime("%m-%d %H:%M"),
        })
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({"notifications": data, "unread_count": unread})


@login_required
@require_POST
def notification_mark_read(request):
    """标记通知已读"""
    data = json.loads(request.body)
    ids = data.get("ids", [])
    if ids:
        Notification.objects.filter(id__in=ids, recipient=request.user).update(is_read=True)
    else:
        # 全部标记已读
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def notification_mark_all_read(request):
    """全部标记已读"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


# ── 题目纠错 ──

@login_required
@require_POST
def submit_report(request, pk):
    """提交题目纠错"""
    from django.utils import timezone as tz
    source = request.POST.get("source", "kaoyan")
    description = request.POST.get("description", "").strip()
    image = request.FILES.get("image")

    if not description:
        return JsonResponse({"ok": False, "msg": "请填写纠错描述"}, status=400)

    # 验证题目存在
    if source == "ai":
        get_object_or_404(AIGeneratedQuestion, pk=pk)
    else:
        get_object_or_404(Question, pk=pk)

    report = QuestionReport.objects.create(
        user=request.user,
        question_id=pk,
        question_source=source,
        description=description,
        image=image if image else None,
    )

    # 通知所有管理员（is_staff）
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if source == "ai":
        q_url = f"/community/ai-question/{pk}/"
    else:
        q_url = f"/community/question/{pk}/"
    for admin in User.objects.filter(is_staff=True):
        Notification.objects.create(
            recipient=admin,
            sender=request.user,
            noti_type="report_new",
            content=f"{request.user.username} 提交了题目纠错（{'AI题' if source == 'ai' else '真题'} #{pk}）",
            url=f"/community/reports/{report.id}/",
        )

    return JsonResponse({"ok": True, "msg": "纠错已提交，审核通过后你将自动获得1天VIP！"})


@login_required
def report_list(request):
    """管理员：纠错审核列表"""
    if not request.user.is_staff:
        return redirect("/")

    reports = QuestionReport.objects.select_related("user").all()

    # 按状态筛选
    status_filter = request.GET.get("status", "pending")
    if status_filter:
        reports = reports.filter(status=status_filter)

    return render(request, "community/report_list.html", {
        "reports": reports,
        "status_filter": status_filter,
    })


@login_required
def report_detail(request, pk):
    """管理员：纠错详情 + 审核"""
    if not request.user.is_staff:
        return redirect("/")

    report = get_object_or_404(QuestionReport, pk=pk)

    # 获取原题信息
    question = None
    if report.question_source == "ai":
        try:
            question = AIGeneratedQuestion.objects.get(pk=report.question_id)
        except AIGeneratedQuestion.DoesNotExist:
            pass
    else:
        try:
            question = Question.objects.get(pk=report.question_id)
        except Question.DoesNotExist:
            pass

    return render(request, "community/report_detail.html", {
        "report": report,
        "question": question,
    })


@login_required
@require_POST
def report_review(request, pk):
    """管理员：审核纠错（采纳/驳回）"""
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "msg": "无权限"}, status=403)

    report = get_object_or_404(QuestionReport, pk=pk)
    if report.status != "pending":
        return JsonResponse({"ok": False, "msg": "该纠错已被审核"}, status=400)

    data = json.loads(request.body)
    action = data.get("action")  # "accept" or "reject"
    reason = data.get("reason", "").strip()

    from django.utils import timezone as tz

    if action == "accept":
        report.status = "accepted"
        report.admin_note = reason
        report.reviewed_by = request.user
        report.reviewed_at = tz.now()
        # 删除上传的图片，释放服务器存储空间
        if report.image:
            try:
                report.image.delete(save=False)
            except Exception:
                pass
        report.save()

        # 给用户延长1天VIP
        report.user.extend_vip(1)

        # 通知用户
        Notification.objects.create(
            recipient=report.user,
            sender=request.user,
            noti_type="report_accepted",
            content=f"你提交的题目纠错已被采纳，奖励1天VIP！",
            url=f"/community/{'ai-question' if report.question_source == 'ai' else 'question'}/{report.question_id}/",
        )
        return JsonResponse({"ok": True, "msg": "已采纳，已奖励用户1天VIP"})

    elif action == "reject":
        if not reason:
            return JsonResponse({"ok": False, "msg": "驳回必须附带原因"}, status=400)
        report.status = "rejected"
        report.admin_note = reason
        report.reviewed_by = request.user
        report.reviewed_at = tz.now()
        # 删除上传的图片，释放服务器存储空间
        if report.image:
            try:
                report.image.delete(save=False)
            except Exception:
                pass
        report.save()

        # 通知用户
        Notification.objects.create(
            recipient=report.user,
            sender=request.user,
            noti_type="report_rejected",
            content=f"你提交的题目纠错被驳回，原因：{reason[:100]}",
            url=f"/community/{'ai-question' if report.question_source == 'ai' else 'question'}/{report.question_id}/",
        )
        return JsonResponse({"ok": True, "msg": "已驳回"})

    return JsonResponse({"ok": False, "msg": "无效操作"}, status=400)


# ── 审核中心 ──

@login_required
def review_center(request):
    """审核中心 - 集中管理纠错审核和资源审核"""
    if not request.user.is_staff:
        return redirect("/")

    from .models import ResourceSubmission
    pending_reports = QuestionReport.objects.filter(status='pending').count()
    pending_submissions = ResourceSubmission.objects.filter(status='pending').count()
    return render(request, "community/review_center.html", {
        "pending_reports": pending_reports,
        "pending_submissions": pending_submissions,
    })


# ── 资源投稿审核 ──

@login_required
def resource_submission_list(request):
    """管理员：资源投稿审核列表"""
    if not request.user.is_staff:
        return redirect("/")

    from .models import ResourceSubmission
    submissions = ResourceSubmission.objects.select_related("user", "category", "school", "subject")

    status_filter = request.GET.get("status", "pending")
    if status_filter:
        submissions = submissions.filter(status=status_filter)

    return render(request, "community/resource_submission_list.html", {
        "submissions": submissions,
        "status_filter": status_filter,
    })


@login_required
def resource_submission_detail(request, pk):
    """管理员：资源投稿详情 + 审核"""
    if not request.user.is_staff:
        return redirect("/")

    from .models import ResourceSubmission
    submission = get_object_or_404(ResourceSubmission, pk=pk)

    return render(request, "community/resource_submission_detail.html", {
        "submission": submission,
    })


@login_required
@require_POST
def resource_submission_review(request, pk):
    """管理员：审核资源投稿（采纳/驳回）"""
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "msg": "无权限"}, status=403)

    from .models import ResourceSubmission
    from django.utils import timezone as tz

    submission = get_object_or_404(ResourceSubmission, pk=pk)
    if submission.status != "pending":
        return JsonResponse({"ok": False, "msg": "该投稿已被审核"}, status=400)

    data = json.loads(request.body)
    action = data.get("action")  # "accept" or "reject"
    reason = data.get("reason", "").strip()

    if action == "accept":
        submission.status = "accepted"
        submission.admin_note = reason
        submission.reviewed_by = request.user
        submission.reviewed_at = tz.now()
        submission.save()

        # 创建正式资源
        from res_center.models import Resource
        resource = Resource.objects.create(
            title=submission.title,
            category=submission.category,
            subject=submission.subject,
            school=submission.school,
            cover=submission.cover,  # ImageField 文件会被保留
            description=submission.description,
            link=submission.link,
            price=submission.price,
            uploaded_by=submission.user,
        )

        # 给用户奖励：1天VIP + 100 coin
        submission.user.extend_vip(1)
        from user.coin_utils import add_coins
        add_coins(submission.user, 100, reason="resource_accepted",
                  description=f"资源投稿被采纳：{submission.title}")

        # 通知用户
        Notification.objects.create(
            recipient=submission.user,
            sender=request.user,
            noti_type="resource_accepted",
            content=f"你投稿的资源「{submission.title}」已被采纳！奖励1天VIP + 100点数",
            url=f"/res-center/{resource.pk}/",
        )
        return JsonResponse({"ok": True, "msg": "已采纳，已创建资源并奖励用户1天VIP + 100点数"})

    elif action == "reject":
        if not reason:
            return JsonResponse({"ok": False, "msg": "驳回必须附带原因"}, status=400)
        submission.status = "rejected"
        submission.admin_note = reason
        submission.reviewed_by = request.user
        submission.reviewed_at = tz.now()
        # 拒绝时删除封面图
        if submission.cover:
            try:
                submission.cover.delete(save=False)
            except Exception:
                pass
        submission.save()

        # 通知用户
        Notification.objects.create(
            recipient=submission.user,
            sender=request.user,
            noti_type="resource_rejected",
            content=f"你投稿的资源「{submission.title}」被驳回，原因：{reason[:100]}",
        )
        return JsonResponse({"ok": True, "msg": "已驳回"})

    return JsonResponse({"ok": False, "msg": "无效操作"}, status=400)
