from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from admin_panel.models import Room


class Housekeeper(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='housekeeper',
                                verbose_name='Учетная запись')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    color = models.CharField(max_length=7, default='#667eea', verbose_name='Цвет в интерфейсе')

    class Meta:
        verbose_name = 'Горничная'
        verbose_name_plural = 'Горничные'

    def get_short_name(self):
        last = self.user.last_name or self.user.user_name
        first = self.user.first_name
        return f'{last} {first[0]}.' if first else last

    def __str__(self):
        return self.get_short_name()


class RoomState(models.Model):
    STATES = [
        ('dirty', 'Грязный'),
        ('cleaned', 'Убрано'),
        ('verified', 'Проверено'),
        ('repair', 'Ремонт'),
    ]

    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='clean_state',
                                verbose_name='Номер')
    state = models.CharField(max_length=20, choices=STATES, default='verified', verbose_name='Состояние')
    updated_at = models.DateField(auto_now=True, verbose_name='Обновлено')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Кем', related_name='+')

    class Meta:
        verbose_name = 'Состояние номера'
        verbose_name_plural = 'Состояние номеров'

    def __str__(self):
        return f'{self.room.room_number}: {self.get_state_display()}'


class CleaningTask(models.Model):
    CLEANING_TYPES = [
        ('current', 'Текущая уборка'),
        ('general', 'Генеральная уборка'),
        ('unsheduled', 'Внеплановая уборка'),
    ]

    DURATIONS = {'current': 20, 'general': 40, 'unsheduled': 30}

    STATES = [
        ('pending', 'Ожидает'),
        ('in_progress', 'В работе'),
        ('done', 'Выполнено'),
        ('verified', 'Проверено')
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='cleaning_tasks',
                             verbose_name='Номер')
    date = models.DateField(default=timezone.localdate, verbose_name='Дата')
    cleaning_type = models.CharField(max_length=20, choices=CLEANING_TYPES, default='current',
                                     verbose_name='Вид уборки')
    duration_min = models.IntegerField(default=20, verbose_name='Подготовка (мин)')
    assignee = models.ForeignKey(Housekeeper, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='cleaning_tasks', verbose_name='Исполнитель')
    state = models.CharField(max_length=20, choices=STATES, default='pending', verbose_name='Состояние')
    notes = models.TextField(blank=True, verbose_name='Заметки')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_cleaning_tasks')
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['date', 'room__room_number']
        verbose_name = 'Задание на уборку'
        verbose_name_plural = 'Задания на уборку'

    def __str__(self):
        return f'{self.room.room_number} {self.date} ({self.get_cleaning_type_display()})'


    def save(self, *args, **kwargs):
        if not self.duration_min:
            self.duration_min = self.DURATIONS.get(self.cleaning_type, 20)



class RepairTask(models.Model):
    STATES = [
        ('pending', 'Ожидает'),
        ('in_progress', 'В работе'),
        ('done', 'Выполнено'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, verbose_name='Номер',
                             related_name='repair_tasks')
    date = models.DateField(default=timezone.localdate, verbose_name='Дата')
    description = models.TextField(verbose_name='Описание')
    assignee = models.ForeignKey(Housekeeper, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='repair_tasks', verbose_name='Исполнитель')
    state = models.CharField(max_length=20, choices=STATES, default='pending', verbose_name='Состояние')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_repair_tasks')



    class Meta:
        ordering = ['date', 'room__room_number']
        verbose_name = 'Заявка на ремонт'
        verbose_name_plural = 'Заявки на ремонт'


    def __str__(self):
        return f'Ремонт {self.room.room_number} {self.date}'