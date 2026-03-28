from django.apps import AppConfig


class UserConfig(AppConfig):
    name = 'user'

    def ready(self):
        import user.signals  # noqa: F401 — 确保信号注册
