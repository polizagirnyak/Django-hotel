from django import forms
from admin_panel.models import Room
from .models import CleaningTask, RepairTask, Housekeeper


class CleaningTaskForm(forms.ModelForm):
    class Meta:
        model = CleaningTask
        fields = ['room', 'date', 'cleaning_type', 'duration_min', 'assignee', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'cleaning_type': forms.Select(attrs={'class': 'form-select'}),
            'duration_min': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 180}),
            'assignee': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = (
            Housekeeper.objects.filter(is_active=True).select_related('user')
        )
        self.fields['assignee'].required = False
        self.fields['assignee'].empty_label = 'Не назначена'
        self.fields['room'].queryset = (
            Room.objects.select_related('room_type').order_by('room_number')
        )
        self.fields['notes'].required = False

class RepairTaskForm(forms.ModelForm):
    class Meta:
        model = RepairTask
        fields = ['room', 'date', 'description', 'assignee']
        widgets = {
            'room': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows':3}),
            'assignee': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = (
            Housekeeper.objects.filter(is_active = True).select_related('user')
        )
        #Назначение горничной
        self.fields['assignee'].required = False
        self.fields['assignee'].empty_label = 'Не назначено'
        self.fields['room'].queryset = (
            Room.objects.select_related('room_type').order_by('room_number')
        )


