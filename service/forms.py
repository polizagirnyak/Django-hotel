from django import forms
from django.db.models import Q

from .models import Service, ServiceCategory, ServiceBooking
from admin_panel.models import Customer
from django.utils import timezone
from datetime import datetime, date, time


class ServiceCategoryForm(forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = ['name', 'description', 'is_active', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows':3})
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'category', 'description', 'short_description',
                  'price', 'duration', 'max_capacity', 'status', 'is_featured',
                  'image', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'short_description': forms.Textarea(attrs={'rows': 2})
        }


class ServiceBookingForm(forms.ModelForm):
    class Meta:
        model = ServiceBooking
        fields = ['customer', 'service', 'booking_date', 'start_time',
                  'participants', 'special_requests', 'notes', 'status']
        widgets = {
            'special_requests': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'booking_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #Ограничиваем выбор даты только будущими датами
        self.fields['booking_date'].widget.attrs['min'] = date.today().isoformat()
        if not self.instance.pk:
            now = timezone.now()
            self.fields['start_time'].initial = time(now.hour + 1, 0)
            self.fields['booking_date'].initial = date.today()

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get('service')
        booking_date = cleaned_data.get('booking_date')
        start_time = cleaned_data.get('start_time')
        participants = cleaned_data.get('participants')

        if service and booking_date and start_time and participants:
            #Проверяем, что дата в будущем
            if booking_date < date.today():
                raise forms.ValidationError('Дата записи не может быть в прошлом')
            #Проверяем кол-во участников
            if participants > service.max_capacity:
                raise forms.ValidationError(f'Максимальное количество участников для этой услуги: {service.max_capacity}')
            #Проверяем доступность услуги(кроме случаев редактирования существующих записей)
            if not self.instance.pk or (self.instance and (self.instance.booking_date != booking_date or self.instance.start_time != start_time)):
                #Расчитываем время окончания
                start_datetime = datetime.combine(booking_date, start_time)
                end_datetime = start_datetime + timezone.timedelta(minutes = service.duration)
                end_time = end_datetime.time()
                #Проверяем пересечения
                overlapping = ServiceBooking.objects.filter(
                    service = service,
                    booking_date = booking_date,
                    status__in = ['confirmed', 'pending', 'in_progress'],
                ).exclude(pk = self.instance.pk).filter(
                    Q(start_time__lt = end_time, end_time__gt = start_time)
                )
                if overlapping.exists():
                    raise forms.ValidationError('В это время улуга уже забронирована, выберите другое время')
        return cleaned_data


