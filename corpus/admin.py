from django.contrib import admin

from .models import (
    AIModel,
    Document,
    Entry,
    Notification,
    ReviewLog,
    Task,
    Theologian,
    TranslationGroup,
)


@admin.register(Theologian)
class TheologianAdmin(admin.ModelAdmin):
    list_display = ("name", "name_en", "tradition")
    search_fields = ("name", "name_en", "tradition")


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "language", "theologian", "is_active")
    list_filter = ("language", "is_active", "theologian")
    search_fields = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(TranslationGroup)
class TranslationGroupAdmin(admin.ModelAdmin):
    list_display = ("source_title",)
    search_fields = ("source_title",)


class EntryInline(admin.TabularInline):
    model = Entry
    extra = 0
    fields = ("order", "verse_ref", "status", "needs_attention", "auto_generated")
    show_change_link = True
    ordering = ("order",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title", "source_type", "content_language", "status",
        "created_by", "created_at",
    )
    list_filter = ("status", "source_type", "content_language", "target_models")
    search_fields = ("title", "author", "raw_text")
    filter_horizontal = ("target_models",)
    autocomplete_fields = ("translation_group",)
    inlines = [EntryInline]
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = (
        "verse_ref", "document", "status", "quality_score",
        "needs_attention", "disputed", "auto_generated",
    )
    list_filter = ("status", "needs_attention", "disputed", "auto_generated")
    search_fields = ("verse_ref", "verse_text", "commentary")
    autocomplete_fields = ("document",)
    readonly_fields = ("id",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("__str__", "assigned_to", "created_by", "is_claimable", "status", "created_at")
    list_filter = ("status", "is_claimable")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "verb", "actor", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("verb", "message")


@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ("entry", "reviewer", "action", "created_at")
    list_filter = ("action",)
