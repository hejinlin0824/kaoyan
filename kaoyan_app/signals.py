import json
from pathlib import Path

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Question

BAK_FILE = Path(__file__).resolve().parent.parent / "bak.json"


def backup_questions():
    """将所有题目序列化为 JSON 写入 bak.json"""
    questions = Question.objects.select_related("school", "question_type").all()
    data = [q.to_dict() for q in questions]
    BAK_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@receiver(post_save, sender=Question)
def on_question_save(sender, instance, **kwargs):
    backup_questions()


@receiver(post_delete, sender=Question)
def on_question_delete(sender, instance, **kwargs):
    backup_questions()