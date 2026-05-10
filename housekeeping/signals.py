from django.db.models.signals import post_save
from django.dispatch import receiver
from admin_panel.models import Room, Booking
from .models import RoomState


@receiver(post_save, sender=Room)
def create_room_state(sender, instance, created, **kwargs):
    if created:
        RoomState.objects.get_or_create(room=instance, defaults={'state':'verified'})


@receiver(post_save, sender=Booking)
def mark_room_dirty_on_checkout(sender, instance, **kwargs):
    if instance.status == 'checked_out':
        state, _ = RoomState.objects.get_or_create(room=instance.room, defaults={'state':'dirty'})
        if state.state not in ('dirty', 'repair'):
            state.state = 'dirty'
            state.save()
