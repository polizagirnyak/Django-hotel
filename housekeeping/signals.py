from django.utils import timezone

from django.db.models.signals import post_save
from django.dispatch import receiver
from admin_panel.models import Room, Booking
from .models import RoomState, CleaningTask


@receiver(post_save, sender=Room)
def create_room_state(sender, instance, created, **kwargs):
    if created:
        RoomState.objects.get_or_create(room=instance, defaults={'state':'verified'})


# @receiver(post_save, sender=Booking)
# def mark_room_dirty_on_checkout(sender, instance, **kwargs):
#     if instance.status == 'checked_out':
#         state, _ = RoomState.objects.get_or_create(room=instance.room, defaults={'state':'dirty'})
#         if state.state not in ('dirty', 'repair'):
#             state.state = 'dirty'
#             state.save()

@receiver(post_save, sender=Booking)
def sync_cleaning_task_for_booking(sender, instance, **kwargs):
    if instance.status == 'confirmed':
        CleaningTask.objects.get_or_create(
            room=instance.room,
            date=instance.check_in_date,
            cleaning_type = 'move_in',
            defaults={
                'duration_min': CleaningTask.DURATIONS['move_in'],
                'notes': f'Автоматически создана для бронирования №{instance.pk}'
            }
        )
    if instance.status == 'check_out':
        task_date = max(instance.check_out_date, timezone.localdate())
        CleaningTask.objects.get_or_create(
            room=instance.room,
            date=task_date,
            cleaning_type = 'departure',
            defaults={
                'duration_min': CleaningTask.DURATIONS['departure'],
                'notes': f'Автоматически создана для бронирования №{instance.pk}'
            }
        )
        state, _ = RoomState.objects.get_or_create(room=instance.room, defaults={'state': 'dirty'})
        if state.state not in ('dirty', 'repair'):
            state.state = 'dirty'
            state.save()


