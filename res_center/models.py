from django.db import models
from django.conf import settings


class ResourceCategory(models.Model):
    """资源分类（视频资料、真题资料等）"""

    ICON_CHOICES = [
        ("fa-folder", "📁 文件夹"),
        ("fa-file", "📄 文件"),
        ("fa-file-pdf", "📕 PDF"),
        ("fa-file-lines", "📝 文档"),
        ("fa-file-image", "🖼️ 图片"),
        ("fa-file-zipper", "📦 压缩包"),
        ("fa-video", "🎬 视频"),
        ("fa-headphones", "🎧 音频"),
        ("fa-book", "📖 书籍"),
        ("fa-book-open", "📕 教材"),
        ("fa-graduation-cap", "🎓 学位"),
        ("fa-pen-fancy", "✏️ 笔记"),
        ("fa-brain", "🧠 知识点"),
        ("fa-lightbulb", "💡 技巧"),
        ("fa-flask", "🧪 实验"),
        ("fa-calculator", "🧮 计算"),
        ("fa-code", "💻 代码"),
        ("fa-database", "🗄️ 数据"),
        ("fa-chart-bar", "📊 图表"),
        ("fa-clipboard-list", "📋 清单"),
        ("fa-star", "⭐ 精选"),
        ("fa-trophy", "🏆 真题"),
        ("fa-shield-halved", "🛡️ 答案"),
        ("fa-puzzle-piece", "🧩 练习"),
        ("fa-fire", "🔥 热门"),
        ("fa-gem", "💎 稀有"),
        ("fa-download", "⬇️ 下载"),
        ("fa-link", "🔗 链接"),
        ("fa-cloud-arrow-up", "☁️ 云资源"),
        ("fa-newspaper", "📰 资讯"),
    ]

    name = models.CharField(max_length=50, unique=True, verbose_name="分类名称")
    icon = models.CharField(max_length=50, choices=ICON_CHOICES, default="fa-folder",
                            verbose_name="图标")
    sort_order = models.IntegerField(default=0, verbose_name="排序（越小越靠前）")

    class Meta:
        verbose_name = "资源分类"
        verbose_name_plural = "资源分类"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class Resource(models.Model):
    """资源"""
    title = models.CharField(max_length=200, verbose_name="标题")
    category = models.ForeignKey(ResourceCategory, on_delete=models.CASCADE,
                                 verbose_name="分类", related_name="resources")
    subject = models.ForeignKey("kaoyan_app.Subject", on_delete=models.SET_NULL,
                                null=True, blank=True, verbose_name="关联专业课")
    school = models.ForeignKey("kaoyan_app.School", on_delete=models.SET_NULL,
                               null=True, blank=True, verbose_name="关联学校")
    cover = models.ImageField(upload_to="resource_covers/%Y%m/", null=True, blank=True,
                              verbose_name="封面图片")
    description = models.TextField(verbose_name="简介",
                                   help_text="支持 Markdown + LaTeX 公式")
    link = models.URLField(verbose_name="资源链接")
    price = models.PositiveIntegerField(default=0, verbose_name="价格（点数）",
                                        help_text="0 表示免费")
    download_count = models.PositiveIntegerField(default=0, verbose_name="下载/获取次数")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, verbose_name="上传者")

    class Meta:
        verbose_name = "资源"
        verbose_name_plural = "资源"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ResourcePurchase(models.Model):
    """资源购买记录"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             verbose_name="用户", related_name="resource_purchases")
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE,
                                 verbose_name="资源", related_name="purchases")
    coins_paid = models.PositiveIntegerField(verbose_name="支付点数")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="购买时间")

    class Meta:
        verbose_name = "资源购买记录"
        verbose_name_plural = "资源购买记录"
        unique_together = [("user", "resource")]

    def __str__(self):
        return f"{self.user.username} - {self.resource.title}"