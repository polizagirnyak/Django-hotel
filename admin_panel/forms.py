from django import forms
from.models import Room, RoomType, Customer, Booking


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = ['name','description', 'price_per_night', 'capacity']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3})
        }

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['room_number', 'room_type', 'status', 'floor', 'features']
