"""Makes the records visible in Django's behind-the-scenes inspection screens (/admin/)."""

from django.contrib import admin

from .models import AccessionEvent, DeaccessionEvent, Evidence, Mystery, Submission


@admin.register(Mystery)
class MysteryAdmin(admin.ModelAdmin):
    list_display = ("id", "display_title", "object_id", "status", "is_sample", "created_at")
    list_filter = ("status", "is_sample")
    search_fields = ("title", "object_id", "original_name")


class EvidenceInline(admin.TabularInline):
    model = Evidence
    extra = 0


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("reference", "person_name", "mystery", "status", "created_at", "decided_at")
    list_filter = ("status",)
    search_fields = ("reference", "person_name")
    inlines = [EvidenceInline]


admin.site.register(AccessionEvent)
admin.site.register(DeaccessionEvent)
