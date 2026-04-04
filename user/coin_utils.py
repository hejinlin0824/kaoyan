"""
站内点数（Coin）工具模块
提供点数增减、每日打卡等公共能力，供各 app 复用。
"""

from django.db import transaction
from django.utils import timezone


def add_coins(user, amount, reason="other", description=""):
    """
    为用户增减点数。

    :param user: User 实例
    :param amount: 变动数量（正数增加，负数扣除）
    :param reason: 变动原因，对应 CoinRecord.REASON_CHOICES
    :param description: 补充说明
    :return: (success: bool, message: str)
    """
    from .models import CoinRecord

    if amount == 0:
        return False, "变动数量不能为0"

    # 扣除时检查余额是否充足
    if amount < 0 and user.coins + amount < 0:
        return False, f"点数不足，当前余额 {user.coins}，无法扣除 {abs(amount)}"

    with transaction.atomic():
        user.coins += amount
        user.save(update_fields=["coins"])
        CoinRecord.objects.create(
            user=user,
            amount=amount,
            reason=reason,
            description=description,
        )

    sign = "+" if amount > 0 else ""
    return True, f"点数变动 {sign}{amount}，当前余额 {user.coins}"


def set_coins(user, amount, description="管理员手动设置"):
    """
    直接设置用户点数（仅管理员使用）。

    :param user: User 实例
    :param amount: 目标点数（不能为负数）
    :param description: 补充说明
    :return: (success: bool, message: str)
    """
    from .models import CoinRecord

    if amount < 0:
        return False, "点数不能为负数"

    diff = amount - user.coins
    if diff == 0:
        return True, f"点数未变化，当前余额 {user.coins}"

    with transaction.atomic():
        user.coins = amount
        user.save(update_fields=["coins"])
        CoinRecord.objects.create(
            user=user,
            amount=diff,
            reason="admin_adjust",
            description=description,
        )

    return True, f"点数已设置为 {amount}"


def get_streak(user):
    """
    计算用户当前连续打卡天数。

    规则：
    - 如果今天已打卡，从今天开始往前数；
    - 如果今天尚未打卡，从昨天开始往前数（streak 不断，给用户一天的缓冲）；
    - 只有前天还没打卡才算真正断了。

    :param user: User 实例
    :return: int 连续天数
    """
    from .models import CoinRecord
    from datetime import timedelta
    from django.utils import timezone

    streak = 0
    check_date = timezone.localdate()

    # 今天还没打卡，从昨天开始数
    if not CoinRecord.objects.filter(
        user=user, reason="daily_checkin", created_at__date=check_date
    ).exists():
        check_date -= timedelta(days=1)

    while True:
        if CoinRecord.objects.filter(
            user=user, reason="daily_checkin", created_at__date=check_date
        ).exists():
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak


def can_daily_checkin(user):
    """
    检查用户今日是否可以打卡（即今日尚未通过打卡获得点数）。

    :param user: User 实例
    :return: bool
    """
    from .models import CoinRecord

    today = timezone.localdate()
    return not CoinRecord.objects.filter(
        user=user,
        reason="daily_checkin",
        created_at__date=today,
    ).exists()


def try_daily_checkin(user, question_count, objective_score):
    """
    尝试每日打卡。

    打卡条件：
    1. 题量 ≥ 5 道
    2. 客观题得分 ≥ 20 分
    3. 今日尚未打卡

    :param user: User 实例
    :param question_count: 题目总数
    :param objective_score: 客观题得分
    :return: (success: bool, message: str)
    """
    # 检查今日是否已打卡
    if not can_daily_checkin(user):
        return False, "今日已打卡，明天再来吧"

    # 检查题量
    if question_count < 5:
        return False, f"题量不足5道（当前{question_count}道），无法打卡"

    # 检查客观题得分
    if objective_score < 20:
        return False, f"客观题得分不足20分（当前{objective_score}分），无法打卡"

    # 打卡成功，+100 点数
    return add_coins(
        user,
        amount=100,
        reason="daily_checkin",
        description=f"每日打卡奖励（题量{question_count}道，客观题{objective_score}分）",
    )