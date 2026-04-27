from collections import defaultdict
from datetime import datetime, timedelta

from dateutil.utils import today
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from admin_panel.models import Booking,Room
from .forms import CleaningTaskForm, CleaningTask
from .models import CleaningTask, Housekeeper, RepairTask, RoomState


def staff_required(view_func):
    """
    Доступ только для сотрудников
    """
    return user_passes_test(lambda u: u.is_staff)(view_func)

#Подписи занятости номера на конкретную дату
OCCUPANCY_LABELS = {
    'free': 'Свободно',
    'stay': 'Проживание',
    'check_out': 'Выезд',
    'check_in': 'Заезд',
    'check_in_out': 'Выезд и Заезд'
}

def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None

def _resolve_target_date(request):
    """
    Определяет рабочую дату по get-параметрам(сегодня, завтра, произвольно)
    """
    preset = request.GET.get('preset', 'today')
    today = timezone.localdate()
    if preset == 'today':
        return today, 'today'
    if preset == 'tomorrow':
        return today+timedelta(days=1), 'tomorrow'
    if preset == 'date':
        d = _parse_date(request.GET.get('date'))
        return d or today, 'date'
    d = _parse_date(request.GET.get('date'))
    if d:
        return d, 'date'
    return today, 'today'

def _occupancy_for_room(room_id, target_date, bookings_by_room):
    """
    Определяет статус занятости конкретного номера на конкретную дату
    Назначение:
    1: Таблица дашборда(свободно, заезд, выезд)
    2: Заполнить колонки выезд и заезд
    3: Подсчитать счетчики занятости номеров
    """
    is_check_in = False
    is_check_out = False
    is_stay = False
    check_in_dt = None
    check_out_dt = None
    guests = 0

    for b in bookings_by_room.get(room_id, []):
        if b.check_in_date == target_date:
            is_check_in = True
        if b.check_out_date == target_date:
            is_check_out = True
        if b.check_in_date < target_date < b.check_out_date:
            is_stay = True
        #Считаем гостя, если бронь покрывает target_date
        if b.check_in_date <= target_date <= b.check_out_date:
            guests += 1
            check_in_dt = check_in_dt or b.check_in_date
            check_out_dt = check_out_dt or b.check_out_date

    if is_check_in and is_check_out:
        status = 'check_in_out'
    elif is_check_out:
        status = 'check_out'
    elif is_check_in:
        status = 'check_in'
    elif is_stay:
        status = 'stay'
    else:
        status = 'free'

    return {
        'status': status,
        'check_in_dt': check_in_dt,
        'check_out_dt': check_out_dt,
        'guests': guests,
    }

def _abbr_room_type(name):
    if not name:
        return ''
    parts = name.upper().replace('Ё', 'Е').split()
    if len(parts) >= 2:
        return ''.join(p[0] for p in parts[:3])
    return name[:3].upper()


@login_required
@staff_required
def dashboard(request):
    """
    Главная страница приложения уборки
    Собирает на одной странице:
    - Сводные карточки(занятость, состояние, виды уборки)
    - Таблицу всех номеров с управлением(исполнитель, состояние)
    - Форма для назначении уборки
    """
    target_date, preset = _resolve_target_date(request)
    today = timezone.localdate()

    rooms = list(Room.objects.select_related('room_type').order_by('room_number'))

    bookings = Booking.objects.filter(
        check_in_date__lte = target_date,
        check_out_date__gte = target_date,
        status__in = ['confirmed', 'checked_in', 'checked_out']
    ).select_related('customer', 'room')

    #Группируем бронирования по номеру комнату
    bookings_by_room = defaultdict(list)
    for b in bookings:
        bookings_by_room[b.room_id].append(b)

    #Задание на уборку на эту дату
    tasks_qs = CleaningTask.objects.filter(date=target_date).select_related(
        'room', 'room__room_type', 'assignee', 'assignee__user',
    )
    tasks_by_room = {t.room_id: t for t in tasks_qs}