from datetime import date

from django import forms
from .models import Room, RoomType, Customer, Booking, Payment


class RoomTypeForm(forms.ModelForm):
    class Meta:
        model = RoomType
        fields = ['name', 'description', 'price_per_night', 'capacity']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название типа'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Опишите особенности этого типа номеров...'
            }),
            'price_per_night': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '2500',
                'step': '0.01',
                'min': '0'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '2',
                'min': '1'
            }),
        }


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['room_number', 'room_type', 'status', 'floor', 'features']
        widgets = {
            'room_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите номер комнаты'
            }),
            'room_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'floor': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Этаж',
                'min': '1'
            }),
            'features': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опишите особенности комнаты...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем CSS классы к полям
        for field_name, field in self.fields.items():
            if field_name != 'features':  # Для textarea стили уже заданы
                field.widget.attrs.update({'class': 'form-input'})


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone', 'passport_number', 'birthday']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите имя'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите фамилию'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'passport_number': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Серия и номер паспорта'}),
            'birthday': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['birthday'].input_formats = ['%Y-%m-%d']
        #Устанавливаем атрибуты для поля Даты
        today = date.today()
        min_date = date(today.year - 120, 1,1)
        self.fields['birthday'].widget.attrs['max'] = today.isoformat()
        self.fields['birthday'].widget.attrs['min'] = min_date.isoformat()

    def clean_birthday(self):
        birthday = self.cleaned_data.get('birthday')
        if birthday:
            today = date.today()
            if birthday > today:
                raise forms.ValidationError('Дата рождения не может быть в будущем')
            age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
            if age < 18:
                raise forms.ValidationError('Клиент должен быть старше 18 лет')
            elif age > 120:
                raise forms.ValidationError('Проверьте корректность даты рождения')
        return birthday

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['room', 'check_in_date', 'check_out_date', 'special_requests']
        widgets = {
            'check_in_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'check_out_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'special_requests': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Особые пожелания...'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        available_rooms = kwargs.pop('available_rooms', None)
        super().__init__(*args, **kwargs)
        self.fields['check_in_date'].input_formats = ['%Y-%m-%d']
        self.fields['check_out_date'].input_formats = ['%Y-%m-%d']
        if available_rooms:
            self.fields['room'].queryset = available_rooms


class BookingEditForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['room', 'check_in_date', 'check_out_date', 'status', 'special_requests', 'total_price']
        widgets = {
            'check_in_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'check_out_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'special_requests': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Особые пожелания...'
            }),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'total_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Можно ограничить выбор комнат только доступными
        self.fields['room'].queryset = Room.objects.all()

        # Добавляем подсказки
        self.fields['total_price'].help_text = 'Автоматически рассчитывается при изменении дат или номера'


class SearchForm(forms.Form):
    check_in = forms.DateField(
        label='Дата заезда',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    check_out = forms.DateField(
        label='Дата выезда',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    room_type = forms.ModelChoiceField(
        queryset=RoomType.objects.all(),
        label='Тип номера',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    capacity = forms.IntegerField(
        label='Минимальная вместимость',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'placeholder': 'Любая'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')

        if check_in and check_out:
            if check_in >= check_out:
                raise forms.ValidationError('Дата выезда должна быть позже даты заезда')
            if check_in < date.today():
                raise forms.ValidationError('Дата заезда не может быть в прошлом')

        return cleaned_data