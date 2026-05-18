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


#Текущая - каждый день, генеральная - каждый 3й день
def _ensure_current_cleanings_for_staus(target_date):
    #Берем только фактическое проживание, без дат заезда и выезда
    stay_bookings = list(Booking.objects.filter(
        status = 'checked_in',
        check_in_date__lt = target_date,
        check_out_date__gt = target_date
    ).select_related('room'))
    occupied_room_ids = {booking.room_id for booking in stay_bookings}

    #Составляем сущ задачи
    existing_tasks = set(
        CleaningTask.objects.filter(
            room_id__in = occupied_room_ids,
            date = target_date
        ).values_list('room_id', 'cleaning_type')
    )

    #Если номер на ремонте, то уборка не производится
    rooms_in_repair = set(
        RoomState.objects.filter(
            room_id__in = occupied_room_ids,
            state = 'repair'
        ).values_list('room_id', flat=True)
    )

    tasks_to_create = []
    dirty_room_ids = set()
    for booking in stay_bookings:
        if booking.room_id in rooms_in_repair:
            continue

        #Считаем порядковый день проживания относительно даты заезда
        days_since_check_in = (target_date - booking.check_in_date).days

        #Генеральная уборка заменяет текущую
        if days_since_check_in > 0 and days_since_check_in % 3 == 0:
            requested_types = ['general']
        else:
            requested_types = ['current']
        for cleaning_type in requested_types:
            if (booking.room_id, cleaning_type) in existing_tasks:
                continue

            tasks_to_create.append(CleaningTask(
                room = booking.room,
                date = target_date,
                cleaning_type = cleaning_type,
                duration_min = CleaningTask.DURATIONS[cleaning_type],
                notes = 'Автоматически создана для текущего проживания'
            ))

            #Новость о плановой уборки должна попасть в задание горничным
            dirty_room_ids.add(booking.room_id)
    if not tasks_to_create:
        return
    CleaningTask.objects.bulk_create(tasks_to_create)

    for room_id in dirty_room_ids:
        state, _ = RoomState.objects.get_or_create(
            room_id = room_id,
            defaults = {'state':'dirty'}
        )
        if state.state not in ('dirty', 'repair'):
            state.state = 'dirty'
            state.save(update_fields=['state', 'updated_at'])







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
    _ensure_current_cleanings_for_staus(target_date)
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


#Вкладка уборки
@login_required
@staff_required
def cleanings_list(request):
    """
    Список всех заданий на уборку за выбранную дату
    Удобен, когда нужно работать с заданиями, а не с комнатами
    :param request:
    :return:
    """
    target_date, preset = _resolve_target_date(request)
    today = timezone.localdate()
    tasks = CleaningTask.objects.filter(date=target_date).select_related(
        'room', 'room__room_type', 'assignee', 'assignee__user'
    ).order_by('room__room_number')

    filt_type = request.GET.get('type', '')
    filt_state = request.GET.get('state', '')
    filt_assignee = request.GET.get('assignee', '')

    if filt_type:
        tasks = tasks.filter(cleaning_type=filt_type)
    if filt_state:
        tasks = tasks.filter(state=filt_state)
    if filt_assignee == 'none':
        tasks = tasks.filter(assignee__isnull=True)
    elif filt_assignee:
        tasks = tasks.filter(assignee_id=filt_assignee)

    housekeepers = Housekeeper.objects.filter(is_active=True).select_related('user')

    context = {
        'target_date': target_date,
        'preset': preset,
        'today': today,
        'tomorrow': today + timedelta(days=1),
        'tasks': tasks,
        'housekeepers': housekeepers,
        'filters': {
            'type': filt_type,
            'state': filt_state,
            'assignee': filt_assignee,
        },
        'cleaning_type_choices': CleaningTask.CLEANING_TYPES,
        'task_state_choices': CleaningTask.STATES,
    }

    return render(request, 'housekeeping/cleanings.html', context=context)


#Создание заданий
@login_required
@staff_required
def assign_cleaning(request):
    if request.method == 'POST':
        form = CleaningTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            messages.success(request, f'Уборка для номера {task.room.room_number} назначена')
            return redirect(f'/housekeeping/?preset=date&date={task.date.isoformat()}')
        #Ошибка валидации
        messages.error(
            request,
            'Ошибки в форме: '
            + '; '.join(f'{k}: {v[0]}' for k, v in form.errors.items()),)
    return redirect('housekeeping_dashboard')

#Создает задание на ремонт, одновременно переводит состояние номера в ремонт
@login_required
@staff_required
def assign_repair(request):
    if request.method == 'POST':
        form = RepairTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            #Параллельно отмечаем номер как в ремонте
            state, _ = RoomState.objects.get_or_create(
                room = task.room,
                defaults={'state': 'repair'}
            )
            state.state = 'repair'
            state.updated_by = request.user
            state.save()
            messages.success(request, f'Ремонт для номера {task.room.room_number} назначен')
            return redirect(f'/housekeeping/?preset=date&date={task.date.isoformat()}')
        messages.error(
            request,
            'Ошибки в форме: '
            + '; '.join(f'{k}: {v[0]}' for k, v in form.errors.items()), )
    return redirect('housekeeping_dashboard')


@login_required
@staff_required
@require_POST
#Меняет состояние номера
def update_room_state(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    new_state = request.POST.get('state')
    if new_state not in dict(RoomState.STATES):
        return JsonResponse({'ok': False, 'error': 'Неизвестное состояние'}, status=400)
    state, _ = RoomState.objects.get_or_create(room=room)
    state.state = new_state
    state.updated_by = request.user
    state.save()

    #Синхронизация состояние с заданием на эту дату
    target_date = _parse_date(request.POST.get('date')) or timezone.localdate()
    task = CleaningTask.objects.filter(room=room, date=target_date).first()
    if task:
        if new_state == 'cleaned':
            task.state = 'done'
            task.completed_at = timezone.now()
        elif new_state == 'verified':
            task.state = 'verified'
            task.completed_at = task.completed_at or timezone.now()
        elif new_state == 'dirty':
            task.state = 'pending'
            task.completed_at = None
        task.save()

    return JsonResponse({
        'ok': True,
        'state': new_state,
        'state_label': dict(RoomState.STATES)[new_state]
    })

@login_required
@staff_required
@require_POST
#Меняет state задачи на уборку и синхронизирует room_state
def update_task_state(request, task_id):
    task = get_object_or_404(CleaningTask, pk=task_id)
    new_state = request.POST.get('state')
    if new_state not in dict(CleaningTask.STATES):
        return JsonResponse({
            'ok': False,
            'error': 'Неизвестное состояние',
        },
        status=400)
    task.state = new_state
    if new_state in ('done', 'verified'):
        task.completed_at = task.completed_at or timezone.now()
    else:
        task.completed_at = None
    task.save()

    #Обратная синхронизация
    room_state, _ = RoomState.objects.get_or_create(room=task.room)
    if new_state == 'done':
        room_state.state = 'cleaned'
    elif new_state == 'verified':
        room_state.state = 'verified'
    elif new_state == 'pending':
        room_state.state = 'dirty'

    room_state.updated_by = request.user
    room_state.save()

    return JsonResponse({
        'ok': True,
        'state': new_state,
        'state_label': dict(CleaningTask.STATES)[new_state],
        'room_state': room_state.state
    })




@login_required
@staff_required
@require_POST
#Назначает или снимает исполнителя в задании таблицы
def assign_housekeeper(request, task_id):
    task = get_object_or_404(CleaningTask, pk=task_id)
    housekeeper_id = request.POST.get('housekeeper_id') or None
    if housekeeper_id:
        task.assignee = get_object_or_404(Housekeeper, pk=housekeeper_id)
    else:
        task.assignee = None
    task.save()
    label = task.assignee.get_short_name() if task.assignee else 'Нет'
    return JsonResponse({
        'ok': True,
        'assignee_label': label,
        'assignee_id': task.assignee_id
    })


@login_required
@staff_required
@require_POST
#Удаляет задание на уборку из контекстного меню строки таблицы
def delete_task(request, task_id):
    task = get_object_or_404(CleaningTask, pk=task_id)
    room_number = task.room.room_number
    task.delete()
    messages.success(request, f'Задание для номера {room_number} удалено')
    return redirect(request.META.get('HTTP_REFERER', 'housekeeping_dashboard'))


@login_required
@staff_required
@require_POST
def delete_repair(request, repair_id):
    repair = get_object_or_404(RepairTask, pk=repair_id)
    room = repair.room
    room_number = room.room_number
    target_date = repair.date
    repair.delete()

    has_active_repairs = RepairTask.objects.filter(
        room = room,
        state__in = ['pending', 'in_progress']
    ).exists()
    if not has_active_repairs:
        state, _ = RoomState.objects.get_or_create(room=room)
        task = CleaningTask.objects.filter(room=room, date=target_date).first()
        if task and task.state in ('pending', 'in_progress'):
            state.state = 'dirty'
        elif task and task.state == 'done':
            state.state = 'cleaned'
        else:
            state.state = 'verified'
        state.updated_by = request.user
        state.save()

    messages.success(request, f'Заявка на ремонт для номер {room_number} удалена')
    return redirect(request.META.get('HTTP_REFERER', 'housekeeping_dashboard'))

















