import os
from celery import Celery

# 绑定 Django 配置文件
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kaoyan_project.settings')

app = Celery('kaoyan_project')

# 从 Django settings 加载配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# ✅ 关键：自动发现所有 App 下的 tasks.py
app.autodiscover_tasks()