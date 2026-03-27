from django.apps import AppConfig


class KaoyanAppConfig(AppConfig):
    name = 'kaoyan_app'

    def ready(self):
        import kaoyan_app.signals  # noqa: F401
