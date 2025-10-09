from django.db import models
from django.core.validators import (MinValueValidator,
                                    MaxValueValidator)


class RoomType(models.Model):
    name = models.CharField(max_length=100, verbose_name='Тип номера')
    description = models.TextField(verbose_name='Описание')
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена за ночь')
    capacity = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(8)], verbose_name='Вместимость')

    def __str__(self):
        return f'{self.name} ({self.capacity} чел.) - {self.price_per_night} руб./ночь'


class Room(models.Model):
    ROOM_STATUS = [
        ('available', 'Свободен'),
        ('occupied', 'Занят'),
        ('maintenance', 'На обслуживании')
    ]
    room_number = models.CharField(max_length=10, unique=True, verbose_name='Номер комнаты')
    room_type = models.ForeignKey(RoomType, on_delete=models.SET_NULL, null=True, verbose_name='Тип номера')
    status = models.CharField(max_length=50, choices=ROOM_STATUS, default='available', verbose_name='Статус')
    floor = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name='Этаж')
    features = models.TextField(blank=True, null=True, verbose_name='Особенности')

    def __str__(self):
        return f'Комната {self.room_number} - {self.room_type.name}'


class Customer(models.Model):
    first_name = models.CharField(max_length=100, verbose_name='Имя')
    last_name = models.CharField(max_length=100, verbose_name='Фамилия')
    email = models.EmailField(verbose_name='Email')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    passport_number = models.CharField(max_length=50, verbose_name='Номер паспорта')
    birthday = models.DateField()

    def __str__(self):
        return f'{self.first_name} {self.last_name} {self.birthday}'

class Booking(models.Model):
    BOOKING_STATUS = [
        ('confirmed', 'Подтверждено'),
        ('checked_in', 'Заселен'),
        ('checked_out', 'Выселен'),
        ('awaiting_payment', 'Ожидает оплаты'),
        ('cancelled', 'Отменено')
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='Клиент')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, verbose_name='Комната')
    check_in_date = models.DateField(verbose_name='Дата заезда')
    check_out_date = models.DateField(verbose_name='Дата выезда')
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='awaiting_payment', verbose_name='Статус')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    special_requests = models.TextField(blank=True, null=True, verbose_name='Особые пожелания')

    def __str__(self):
        return f'Бронирование {self.pk} - {self.customer}'

class Payment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Ожидает'),
        ('comleted', 'Завершен'),
        ('failed', 'Неудачный'),
        ('refunded', 'Возвращен')
    ]
    PAYMENT_METHOD = [
        ('credit_card', 'Банковская карта'),
        ('cash', 'Наличные'),
        ('on_site', 'На сайте'),
    ]
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, verbose_name='Бронирование')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма')
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата оплаты')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='credit_card', verbose_name='Способ оплаты')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS,default= 'pending', verbose_name='Статус')

    def __str__(self):
        return f'Платеж {self.pk} - {self.amount} руб.'



