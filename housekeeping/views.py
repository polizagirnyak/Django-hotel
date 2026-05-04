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
from .forms import CleaningTaskForm, CleaningTask, RepairTaskForm
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

    #Текущее состояние каждого номера
    states = {rs.room_id: rs for rs in RoomState.objects.filter(room__in=rooms)}

    #Параметры фильтрев
    filt_occupancy = request.GET.get('occupancy', '')
    filt_state = request.GET.get('state', '')
    filt_type = request.GET.get('type', '')
    filt_assignee = request.GET.get('assignee', '')
    filt_room_search = request.GET.get('room', '').strip()

    #Сборка данных для сводных карточек
    rows = []
    occ_counts = defaultdict(int)
    state_counts = defaultdict(int)
    type_counts = defaultdict(int)
    type_counts_all = 0
    total_minutes = 0

    for room in rooms:
        occ = _occupancy_for_room(room.id, target_date, bookings_by_room)
        state = states.get(room.id)
        state_key = state.state if state else 'verified'
        task = tasks_by_room.get(room.id)

        #Считаем счетчики до применения фильтров(отражаем весь отель)
        occ_counts[occ['status']] += 1
        state_counts[state_key] += 1
        if task:
            type_counts[task.cleaning_type] += 1
            type_counts_all += 1
            total_minutes += task.duration_min or 0

        #Применияем фильтры(отсекаем строки, которые не подходят)
        if filt_room_search and filt_room_search.lower() not in str(room.room_number).lower():
            continue
        if filt_occupancy and filt_occupancy != occ['status']:
            continue
        if filt_type and (not task or task.cleaning_type != filt_type):
            continue
        if filt_assignee == 'none':
            if task and task.assignee_id:
                continue
        elif filt_assignee:
            if not task or str(task.assignee_id) != filt_assignee:
                continue

        rows.append({
            'room': room,
            'room_type_abbr': _abbr_room_type(room.room_type.name) if room.room_type else '',
            'occupancy': occ,
            'occupancy_label': OCCUPANCY_LABELS[occ['status']],
            'state': state_key,
            'state_obj': state,
            'task': task,
        })

        #Кол-во активных ремонтов на дату
        repairs_count = RepairTask.objects.filter(
            date = target_date,
            state__in = ['pending', 'in_progress']
        ).count()

        housekeepers = Housekeeper.objects.filter(is_active = True).select_related('user')

        #Заранее заполненные формы для модальных окон
        cleaning_form = CleaningTaskForm(initial={'date':target_date})
        repair_form = RepairTaskForm(initial={'date':target_date})

        context = {
            'target_date': target_date,
            'preset': preset,
            'today': today,
            'tomorrow': today+timedelta(days=1),
            'rows': rows,
            'occ_counts': dict(occ_counts),
            'state_counts': dict(state_counts),
            'type_counts': dict(type_counts),
            'type_counts_all': type_counts_all,
            'total_minutes_rest': total_minutes % 60,
            'total_hours': total_minutes // 60,
            'repairs_count': repairs_count,
            'housekeepers': housekeepers,
            'filters': {
                'occupancy': filt_occupancy,
                'state':filt_state,
                'type': filt_type,
                'assignee': filt_assignee,
                'room':filt_room_search,
            },
            'cleaning_form': cleaning_form,
            'repair_form': repair_form,
            'state_choices': RoomState.STATES,
            'cleaning_type_choices': CleaningTask.CLEANING_TYPES,
            'occupancy_choices': list(OCCUPANCY_LABELS.items()),
        }
        return render(request, 'housekeeping/dashboard.html', context=context)








