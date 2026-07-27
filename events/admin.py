from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'event_type',
        'timestamp',
        'location',
    )

    list_filter = (
        'event_type',
        'timestamp',
    )

    search_fields = (
        'event_type',
        'location',
    )