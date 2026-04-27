from django.contrib import admin
from .models import Housekeeper, RoomState, CleaningTask, RepairTask


@admin.register(Housekeeper)
class HousekeeperAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'is_active', 'color')
    list_filter = ('is_active',)
    search_fields = ('user__user_name', 'user__first_name', 'user__last_name')

@admin.register(RoomState)
class RoomStateAdmin(admin.ModelAdmin):
    list_display = ('room', 'state', 'updated_at', 'updated_by')
    list_filter = ('state',)

@admin.register(CleaningTask)
class CleaningTaskAdmin(admin.ModelAdmin):
    list_display = ('room', 'date', 'cleaning_type', 'duration_min', 'assignee', 'state')
    list_filter = ('cleaning_type', 'state', 'date')
    date_hierarchy = 'date'
    autocomplete_fields = ('assignee',)

@admin.register(RepairTask)
class RepairTaskAdmin(admin.ModelAdmin):
    list_display = ('room', 'date', 'assignee', 'state')
    list_filter = ('state', 'date')



