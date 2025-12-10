from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

from admin_panel.models import Customer
from datetime import timedelta

class ServiceCategory(models.Model):
    """
    Категории услуг(спа, ресторан и тд)
    """
    name = models.CharField(max_length=100, verbose_name='Название категории')
    description = models.TextField(verbose_name='Описание категории', blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    order = models.IntegerField(default=0, verbose_name='Порядок отображения')

    class Meta:
        verbose_name = 'Категория услуг'
        verbose_name_plural = 'Категории услуг'
        ordering = [
            'order',
            'name'
        ]
    def __str__(self):
        return self.name


class Service(models.Model):
    """
    Услуги отеля
    """
    SERVICE_STATUS = [
        ('available', 'Доступна'),
        ('unavailable', 'Недоступна'),
        ('seasonal', 'Сезонная')
    ]
    DURATION_CHOICES = [
        (30, '30 минут'),
        (60, '60 минут'),
        (90, '1,5 часа'),
        (120, '2 часа'),
        (180, '3 часа')
    ]
    name = models.CharField(max_length=200, verbose_name='Название услуги')
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE,
                                 verbose_name='Категория', related_name='services')
    description = models.TextField(verbose_name='Подробное описание')
    short_description = models.CharField(max_length=255, verbose_name='Краткое описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    duration = models.IntegerField(choices=DURATION_CHOICES, default=60, verbose_name='Продолжительность')
    max_capacity = models.IntegerField(default=1, verbose_name='Максимальное количество участников')
    status = models.CharField(max_length=20, verbose_name='Статус', choices=SERVICE_STATUS, default='available')
    is_featured = models.BooleanField(default=False, verbose_name='Рекомендуемая услуга')
    image = models.ImageField(upload_to='services/', blank=True, null=True, verbose_name='Изображение')
    order = models.IntegerField(default=0, verbose_name='Порядок отображения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуга'
        ordering = [
            'order',
            'name'
        ]

    def __str__(self):
        return f'{self.name} - {self.price} руб.'

    def duration_display(self):
        """
        Отображение продолжительности в читаемом формате
        :return:
        """
        hours = self.duration // 60
        minutes = self.duration % 60

        if hours > 0 and minutes >0:
            return f'{hours} ч {minutes} мин'
        elif hours > 0:
            return f'{hours} ч'
        else:
            return f'{minutes} мин'


class ServiceBooking(models.Model):
    """
    Запись на услуги
    """
    BOOKING_STATUS = [
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтверждена'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
        ('no_show', 'Не явился')
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name='Клиент', related_name='service_bookings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='bookings', verbose_name='Услуга')
    booking_date = models.DateField(verbose_name='Дата записи')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания', blank=True, null=True)
    participants = models.IntegerField(default=1, verbose_name='Количество участников')
    status = models.CharField(max_length=20, verbose_name='Статус записи', choices=BOOKING_STATUS)
    special_requests = models.TextField(blank=True, null=True, verbose_name='Особые пожелания')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость')
    notes = models.TextField(blank=True, null=True, verbose_name='Примечания администратора')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, verbose_name='Создал', related_name='created_service_bookings')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')

    class Meta:
        verbose_name = 'Запись на услугу'
        verbose_name_plural = 'Записи на услуги'
        ordering = [
            '-booking_date',
            '-start_time'
        ]
        indexes = [
            models.Index(fields=['booking_date', 'start_time']),
            models.Index(fields=['status'])
        ]

    def save(self, *args, **kwargs):
        """
        Автоматически рассчитываем время окончания и стоимость
        :param args:
        :param kwargs:
        :return:
        """
        if not self.end_time and self.service:
            start_datetime = datetime.combine(self.booking_date, self.start_time)
            end_time = start_datetime + timedelta(minutes=self.service.duration)
            self.end_time = end_time.time()

        if not self.total_price:
            self.total_price = self.service.price * self.participants

        super().save(*args, **kwargs)

    def __str__(self):
        return f'Запись #{self.id}: {self.customer} - {self.service.name} ({self.booking_date})'




