import re

from django import forms
from django.core.exceptions import ValidationError
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
                  'image', 'order', 'min_booking_hours']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'short_description': forms.Textarea(attrs={'rows': 2})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['min_booking_hours'].help_text = (
            'Клиенты смогут бронировать услугу не ранее чем за указанное количество часов до времени посещения'
        )


class ServiceBookingForm(forms.ModelForm):
    new_customer = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class':'form-check-input'}),
        label='Новый клиент'
    )

    new_first_name = forms.CharField(
        max_length=100,
        required=False,
        label='Имя',
        widget=forms.TextInput(attrs={'class':'form-control'})
    )

    new_last_name = forms.CharField(
        max_length=100,
        required=False,
        label='Фамилия',
        widget=forms.TextInput(attrs={'class':'form-control'})
    )

    new_phone = forms.CharField(
        max_length=20,
        required=False,
        label='Телефон',
        widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'+79991234567'})
    )

    new_email = forms.EmailField(
        max_length=100,
        required=False,
        label='email',
        widget=forms.TextInput(attrs={'class':'form-control'})
    )

    new_passport_number = forms.CharField(
        max_length=12,
        required=False,
        label='Номер паспорта',
        widget=forms.TextInput(attrs={'class':'form-control'})
    )
    new_birthday = forms.DateField(
        required=False,
        label='Дата рождения',
        widget=forms.DateInput(attrs={'class':'form-control', 'type':'date'})
    )

    class Meta:
        model = ServiceBooking
        fields = ['customer', 'service', 'booking_date', 'start_time',
                  'participants', 'special_requests', 'notes', 'status']
        widgets = {
            'special_requests': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'booking_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'customer': forms.Select(attrs={'class':'form-select'}),
            'service': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'participants': forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #Делаем поле Customer необязательным
        self.fields['customer'].required = False

        #Ограничиваем выбор даты только будущими датами
        self.fields['booking_date'].widget.attrs['min'] = date.today().isoformat()

        #Если выбрана услуга, устанавливаем мин дата,время
        service = None
        if self.initial.get('service'):
            service_id = self.initial.get('service')
            service = Service.objects.get(pk=service_id)
        elif self.data.get('service'):
            try:
                service = Service.objects.get(pk=self.data.get('service'))
            except(Service.DoesNotExist, ValueError):
                pass
        if service and service.min_booking_hours > 0:
            #Расчитываем мин доступное время
            min_datetime = timezone.now()+timezone.timedelta(hours=service.min_booking_hours)
            min_date = min_datetime.date()
            self.fields['booking_date'].widget.attrs['min'] = min_date.isoformat()
        #Если это новая запись, то устанавливаем время по умолчанию
        if not self.instance.pk:
            now = timezone.now()

            if service and service.min_booking_hours > 0:
                min_time = now+timezone.timedelta(hours=service.min_booking_hours)
                self.fields['booking_date'].initial=min_time.date()
                initial_hour = min_time.hour
                if min_time.minute > 30:
                    initial_hour = (initial_hour+1) % 24
                    if initial_hour == 0:
                        self.fields['booking_date'].initial=min_time.date()+timezone.timedelta(days=1)
            else:
                self.fields['booking_date'].initial=date.today()
                initial_hour = (now.hour+1) % 24
            self.fields['start_time'].initial=time(initial_hour, 0)

    def clean(self):
        cleaned_data = super().clean()

        new_customer = cleaned_data.get('new_customer')
        service = cleaned_data.get('service')
        booking_date = cleaned_data.get('booking_date')
        start_time = cleaned_data.get('start_time')
        participants = cleaned_data.get('participants')
        customer = cleaned_data.get('customer')

        # Проверка: должен быть выбран существующий клиент ИЛИ создан новый
        if not new_customer and not customer:
            self.add_error('customer', 'Необходимо выбрать клиента или создать нового')
            self.add_error('new_customer', 'Выберите существующего клиента или создайте нового')
        elif new_customer and customer:
            # Нельзя одновременно выбрать и создать клиента
            self.add_error('new_customer', 'Нельзя одновременно выбрать существующего клиента и создать нового')
            self.add_error('customer', 'Либо выберите существующего клиента, либо создайте нового')

        # Проверяем данные нового клиента
        if new_customer:
            first_name = cleaned_data.get('new_first_name')
            last_name = cleaned_data.get('new_last_name')
            phone = cleaned_data.get('new_phone')

            if not first_name:
                self.add_error('new_first_name', 'Обязательное поле')
            if not last_name:
                self.add_error('new_last_name', 'Обязательное поле')
            if not phone:
                self.add_error('new_phone', 'Обязательное поле')
            else:
                # Очищаем номер для проверки уникальности
                clean_phone = re.sub(r'[^\d+]', '', phone)

                # Нормализуем формат
                if clean_phone.startswith('7') and not clean_phone.startswith('+7'):
                    clean_phone = '+7' + clean_phone[1:]
                elif clean_phone.startswith('8'):
                    clean_phone = '+7' + clean_phone[1:]
                elif not clean_phone.startswith('+'):
                    clean_phone = '+7' + clean_phone

                if len(clean_phone) == 12 and re.match(r'^\+7\d{10}$', clean_phone):
                    cleaned_data['new_phone'] = clean_phone

                    if Customer.objects.filter(phone=clean_phone).exists():
                        self.add_error('new_phone', 'Клиент с таким номером телефона уже существует')
                else:
                    self.add_error('new_phone', 'Введите корректный номер телефона в формате +7XXXXXXXXXX')

        # Валидация услуги и времени
        if service and booking_date and start_time:
            current_datetime = timezone.now()
            booking_datetime = timezone.make_aware(
                datetime.combine(booking_date, start_time)
            )

            # Проверка минимального времени бронирования
            if service.min_booking_hours > 0:
                min_booking_datetime = current_datetime + timezone.timedelta(
                    hours=service.min_booking_hours
                )

                if booking_datetime < min_booking_datetime:
                    min_time_str = min_booking_datetime.strftime('%d.%m.%Y %H:%M')
                    self.add_error(None,
                                   f"Эту услугу можно бронировать не ранее чем за {service.min_booking_hours} "
                                   f"часов до времени посещения. Можно выбрать время с: {min_time_str}"
                                   )

            # Проверка, что время в будущем
            if booking_datetime <= current_datetime:
                self.add_error(None, "Дата и время записи должны быть в будущем")

            # Проверка количества участников
            if participants and service:
                if participants > service.max_capacity:
                    self.add_error('participants',
                                   f"Максимальное количество участников для этой услуги: {service.max_capacity}"
                                   )
                elif participants < 1:
                    self.add_error('participants', "Количество участников должно быть не менее 1")

            # Проверка доступности времени
            if service and booking_date and start_time and participants:
                start_datetime = datetime.combine(booking_date, start_time)
                end_datetime = start_datetime + timezone.timedelta(minutes=service.duration)
                end_time = end_datetime.time()

                overlapping = ServiceBooking.objects.filter(
                    service=service,
                    booking_date=booking_date,
                    status__in=['confirmed', 'pending', 'in_progress'],
                ).exclude(pk=self.instance.pk).filter(
                    Q(start_time__lt=end_time, end_time__gt=start_time)
                )

                if overlapping.exists():
                    self.add_error(None,
                                   "В это время услуга уже забронирована. Выберите другое время."
                                   )

        return cleaned_data

    def save(self, commit = True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('new_customer'):
            customer = Customer.objects.create(
                first_name = self.cleaned_data['new_first_name'],
                last_name = self.cleaned_data['new_last_name'],
                phone = self.cleaned_data['new_phone'],
                email = self.cleaned_data.get('new_email', ''),
                passport_number = self.cleaned_data.get('new_passport_number', ''),
                birthday = self.cleaned_data.get('new_birthday')
            )
            instance.customer = customer
        elif self.cleaned_data.get('customer'):
            instance.customer = self.cleaned_data.get('customer')
        else:
            raise ValidationError('Не указан клиент для бронирования')
        if commit:
            instance.save()
            self.save_m2m()
        return instance

class QuickCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone', 'passport_number', 'birthday']
        widgets = {
            'birthday': forms.DateInput(attrs={'type': date})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['email', 'passport_number', 'birthday']:
            self.fields[field].required = False

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            #Подчищаем номер от лишних символов
            phone = re.sub(r'[^\d+]', '', phone)

            #Проверяем формат номера
            if not re.match(r'^\+?[1-9]\d[5,14]$', phone):
                raise forms.ValidationError('Введите корректный номер телефона')

            #Проверяем, существует ли клиент с таким номером
            if Customer.objects.filter(phone=phone).exists():
                raise forms.ValidationError('Клиент с таким номером уже существует')
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if Customer.objects.filter(email=email).exists():
                raise forms.ValidationError('Клиент с таким email уже существует')
        return email







