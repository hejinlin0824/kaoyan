import json
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_GET

from kaoyan_app.models import Question
from ai_test.models import AIGeneratedQuestion
from .models import Comment, CommentLike, Notification


def _get_discuss_context(question_id, source, extra_context=None):
    """通用：获取讨论区上下文"""
    qs = Comment.objects.filter(question_id=question_id, question_source=source)

    # 获取所有顶级评论
    comments = list(qs.filter(parent__isnull=True).annotate(
        like_count=Count("likes", distinct=True),
        reply_count=Count("replies", distinct=True),
    ))
    comments.sort(key=lambda c: (c.like_count + c.reply_count, c.created_at), reverse=True)

    # 预加载回复
    reply_map = {}
    all_replies = qs.filter(parent__isnull=False).annotate(like_count=Count("likes", distinct=True))
    for r in all_replies:
        reply_map.setdefault(r.parent_id, []).append(r)
    for c in comments:
        c.replies_list = sorted(
            reply_map.get(c.id, []),
            key=lambda r: (r.like_count, r.created_at), reverse=True,
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

    return render(request, "community/question_discuss.html", {
        "question": question,
        "question_source": "kaoyan",
        "comments": ctx["comments"],
        "liked_ids": liked_ids,
        "comment_count": ctx["comment_count"],
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

    return render(request, "community/ai_question_discuss.html", {
        "question": question,
        "question_source": "ai",
        "comments": ctx["comments"],
        "liked_ids": liked_ids,
        "comment_count": ctx["comment_count"],
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
