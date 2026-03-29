from django.contrib import admin
from django.utils.html import format_html
from .models import ResourceCategory, Resource, ResourcePurchase


@admin.register(ResourceCategory)
class ResourceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "icon_display", "sort_order"]
    search_fields = ["name"]

    def icon_display(self, obj):
        """在列表页展示图标预览"""
        return format_html(
            '<i class="fa-solid {}" style="font-size:18px;color:#3b82f6;margin-right:6px;"></i> {}',
            obj.icon, obj.get_icon_display()
        )
    icon_display.short_description = "图标"
    icon_display.allow_tags = True


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "school", "subject", "price", "download_count", "created_at"]
    list_filter = ["category", "school", "subject"]
    search_fields = ["title", "description"]
    readonly_fields = ["download_count", "created_at", "updated_at"]


@admin.register(ResourcePurchase)
class ResourcePurchaseAdmin(admin.ModelAdmin):
    list_display = ["user", "resource", "coins_paid", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__username", "resource__title"]
    readonly_fields = ["created_at"]