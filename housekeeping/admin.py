from django.contrib import admin
from .models import Housekeeper, RoomState, CleaningTask, RepairTask


@admin.register(Housekeeper)
class HousekeeperAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'is_active', 'color')
    list_filter = ('is_active',)
    search_fields = ('user__user_name', 'user__first_name', 'user__last_name')

