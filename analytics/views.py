import json
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal

from django.db.models import Count, Sum

from admin_panel.models import Booking, Payment, Room, RoomType
from service.models import ServiceBooking

from django.shortcuts import render


RU_MONTHS = [
    '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль',
    'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
]

RU_MONTHS_GEN = [
    '', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
    'августа', 'сентября', 'октября', 'ноября', 'декабря'
]

def _month_label(d):
    return f'{RU_MONTHS[d.month]} {d.year}'

def _bookings_for_period(start, end, room_type_id=None):
    """
    Возвращает бронирования пересекающиеся с заданым периодом(отмененные бронирования исключаются)
    при указании room_type фильтрует по типу номера
    :param start:
    :param end:
    :param room_type_id:
    :return:
    """
    bookings = Booking.objects.filter(
        check_in_date__lte = end,
        check_out_date__gte = start,
    ).exclude(status='cancelled').select_related('room', 'room__room_type')
    if room_type_id:
        bookings = bookings.filter(room__room_type_id = room_type_id)
    return bookings


def _occ_stats(bookings, start, end, total_rooms):
    """
    Рассчитывает статистику загрузку номерного фонда
    Для каждого бронирования считается кол-во ночей, попадающих в период
    Возвращает кортеж:
    occupied - суммарного кол-во занятых ночей по номерам
    total_room_nights - общее кол-во доступных ночей(кол-во номеров * кол-во дней)
    pct - процент загрузки(occupied/total_rooms)
    """
    days = (end - start).days or 1
    total_room_nights = total_rooms*days
    occupied = 0
    for b in bookings:
        b_start = max(b.check_in_date, start)
        b_end = min(b.check_out_date, end)
        occupied += max((b_end-b_start).days, 0)
    #Процент загрузки отеля
    pct = round(occupied / total_rooms * 100, 1) if total_room_nights else 0
    return occupied, total_room_nights, pct


def dashboard(request):
    """
    Главная страница аналитики - дашборд
    :param request:
    :return:
    """
    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    #Выбор периода из get параметров, поддерживаются пресеты(месяц, пред.месяц, квартал, пред.квартал)
    preset = request.GET.get('preset', 'month')
    #Произвольный диапозон дат
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date and end_date:
        try:
            month_start = date.fromisoformat(start_date)
            month_end = date.fromisoformat(end_date)
            preset = 'custom'
        except ValueError:
            month_start = today.replace(day=1)
            month_end = today
    #Вычисление границ периода
    else:
        if preset == 'prev_month':
            month_end = today.replace(day=1) - timedelta(days=1)
            month_start = month_end.replace(day=1)
        elif preset == 'quarter':
            q_start_month = ((today.month - 1) // 3) * 3 + 1
            month_end = today
            month_start = today.replace(month=q_start_month, day=1)
        elif preset == 'prev_quarter':
            q_start_month = ((today.month - 1) // 3) * 3 + 1
            month_end = today.replace(month=q_start_month, day=1) - timedelta(days=1)
            month_start = month_end.replace(month=((month_end.month - 1) // 3) * 3 + 1, day=1)
        elif preset == 'year':
            month_start = today.replace(month=1, day=1)
            month_end = today
        else:
            month_start = today.replace(day=1)
            month_end = today
    if month_start > month_end:
        month_start, month_end = month_end, month_start

    period_days = (month_end - month_start).days or 1
    period_label = f'{month_start.strftime('%d.%m.%Y')} - {month_end.strftime('%d.%m.%Y')}'

    #Предыдущий аналогичный период для сравнения KPI
    prev_month_start = month_start - timedelta(days=period_days)
    prev_month_end = month_start - timedelta(days=1)

    #Загружаем бронирования текущего и предыдущего периодов в память
    total_rooms = Room.objects.count() or 1
    cur_bookings = list(_bookings_for_period(month_start, month_end))
    prev_bookings = list(_bookings_for_period(prev_month_start, prev_month_end))

    #Выручка - Сумма total_price всех бронирований
    cur_revenue = sum((b.total_price for b in cur_bookings), Decimal('0'))
    prev_revenue = sum((b.total_price for b in prev_bookings), Decimal('0'))
    #Процент изменения выручки относительно текущего периода
    revenue_diff = round((cur_revenue - prev_revenue) / prev_revenue * 100, 1) if prev_revenue else None

    #Загрузка - Рассчитываем % занятости номерного фонда для обоих периодов
    cur_occ, cur_room_nights, cur_occ_pct = _occ_stats(cur_bookings, month_start, month_end, total_rooms)
    prev_occ, prev_room_nights, prev_occ_pct = _occ_stats(prev_bookings, prev_month_start, prev_month_end, total_rooms)
    occ_diff = round(cur_occ_pct - prev_occ_pct, 1)

    #ADR Средняя цена за проданную ночь
    #Формула: Выпучка/кол-во проданных ночей
    cur_adr = round(cur_revenue / cur_occ, 0) if cur_occ else Decimal('0')
    prev_adr = round(prev_revenue / prev_occ, 0) if prev_occ else Decimal('0')
    adr_diff = round((cur_adr - prev_adr) / prev_adr * 100, 1) if prev_adr else None

    #Средняя выручка от 1 номера за определенный период
    #Формула: выручка/общее кол-во номера ночей, включая свободные
    cur_revpar = round(cur_revenue / cur_room_nights, 0) if cur_room_nights else Decimal('0')
    prev_revpar = round(prev_revenue / prev_room_nights, 0) if prev_room_nights else Decimal('0')
    revpar_diff = round((cur_revpar - prev_revpar) / prev_revpar * 100, 1) if prev_revpar else None


    #График загрузки по дням выбранного месяца
    days_count = (month_end - month_start).days + 1
    daily_occ = []
    #Считаем сколько номеров занято в этот день, день заезда - занят, день выезда - нет
    for i in range(days_count):
        d = month_start + timedelta(days=i)
        occupied = sum(1 for b in cur_bookings if b.check_in_date <= d < b.check_out_date)
        pct = round(occupied / total_rooms * 100, 1) if total_rooms else 0
        if pct < 70: # Голубой - низкая загрузка
            color = 'rgba(99, 179, 237, 0.8)'
        elif pct < 85: # Синий - средняя загрузка
            color = 'rgba(102, 126, 234, 0.8)'
        else: # Фиолетовый - высокая загрузка
            color = 'rgba(118, 75, 162, 0.85)'
        daily_occ.append({'label': d.strftime('%d.%m'), 'pct': pct, 'color': color})

    #Распределение загрузки по типам номеров
    #для каждого типа номера считаем долю занятых ночей от общего числа ночей
    room_types = list(RoomType.objects.annotate(room_count=Count('room')))
    donut_labels = []
    donut_data = []
    donut_colors = ['#667eea', '#764ba2', '#f6ad55', '#fc8181', '#68d391']

    #Суммируем кол-во занятых ночей для бронирований данного типа номера
    for rt in room_types:
        rt_occ = sum(
            max((min(b.check_out_date, month_end) - max(b.check_in_date, month_start)).days, 0)
            for b in cur_bookings if b.room.room_type_id == rt.id
        )
        rt_pct = round(rt_occ / cur_room_nights * 100, 1) if cur_room_nights else 0
        donut_labels.append(rt.name)
        donut_data.append(rt_pct)
    free_pct = round(max(100 - cur_occ_pct, 0), 1)
    donut_labels.append('Свободный')
    donut_data.append(free_pct)
    donut_colors = donut_colors[:len(donut_labels) - 1] + ['#e2e8f0']

    #Статусы бронирований
    #Агрегируем кол-во бронирований по каждому статусу по всей бд
    all_statuses = Booking.objects.values('status').annotate(cnt = Count('id'))
    status_map = {s['status']: s['cnt'] for s in all_statuses}

    #Кол-во выселений за выбранный период
    checked_out_month = Booking.objects.filter(
        status = 'checked_out',
        check_out_date__gte = month_start,
        check_out_date__lte=month_end,
    ).count()

    #Заезды/выезды(всегда относительно сегоднящнего дня, независимо от периода)
    tomorrow = today+timedelta(days=1)
    weekend = today+timedelta(days=6)

    #Заезды и выезды за сегодня
    ci_today = Booking.objects.filter(check_in_date = today).exclude(status = 'cancelled').count()
    co_today = Booking.objects.filter(check_out_date = today).exclude(status = 'cancelled').count()

    #Заезды на завтра
    ci_tomorrow = Booking.objects.filter(check_in_date = tomorrow).exclude(status = 'cancelled').count()

    #Общее кол-во заездов и выездов на ближ неделю
    total_week = Booking.objects.filter(
        check_in_date__gte = today,
        check_in_date__lte = weekend,
    ).exclude(status = 'cancelled').count() + Booking.objects.filter(
        check_out_date__gte=today,
        check_out_date__lte=weekend,
    ).exclude(status = 'cancelled').count()

    #Услуги за выбранный период
    #Фильтруем бронирования услуг по дате
    svc_qs = ServiceBooking.objects.filter(
        booking_date__gte = month_start,
        booking_date__lte = month_end
    ).exclude(status = 'cancelled')

    #Общая выручка бронирований и услуг
    svc_revenue = svc_qs.aggregate(t = Sum('total_price'))['t'] or Decimal('0')
    svc_count = svc_qs.count()

    #Кол-во ожидающих подтверждение
    svc_pending = ServiceBooking.objects.filter(status = 'pending').count()

    #Самая популярная категория услуг по кол-ву бронирований
    popular = (
        svc_qs.values('service__category__name')
        .annotate(cnt=Count('id'))
        .order_by('-cnt').first()
    )
    popular_name = popular['service__category__name'] if popular else '-'

    context = {
        'title': 'Дашборд аналитики',
        'preset': preset,
        'start_date': month_start.isoformat(),
        'end_date': month_end.isoformat(),
        'period_label': period_label,
        'cur_occ_pct': cur_occ_pct,
        'occ_diff': occ_diff,
        'cur_revenue': cur_revenue,
        'revenue_diff': revenue_diff,
        'cur_adr': int(cur_adr),
        'adr_diff': adr_diff,
        'cur_revpar': int(cur_revpar),
        'revpar_diff': revpar_diff,
        'daily_occ_json': json.dumps(daily_occ),
        'donut_labels_json': json.dumps(donut_labels),
        'donut_data_json': json.dumps(donut_data),
        'donat_colors_json': json.dumps(donut_colors),
        'status_confirmed': status_map.get('confirmed', 0),
        'status_checked_in': status_map.get('checked_in', 0),
        'status_awaiting': status_map.get('awaiting_payment', 0),
        'status_cancelled': status_map.get('cancelled', 0),
        'checked_out_month': checked_out_month,
        'ci_today': ci_today,
        'co_today': co_today,
        'ci_tomorrow': ci_tomorrow,
        'total_week': total_week,
        'svc_count': svc_count,
        'svc_revenue': svc_revenue,
        'popular_name': popular_name,
        'svc_pending': svc_pending
    }
    return render(request, template_name='analytics/dashboard.html', context=context)

def report(request):
    """
    Детальный аналитический отчет с расширенными метриками
    Помимо дашборда, включает:
    - сравнение с аналогичными периодом прошлого года
    - кривую пикапа бронирования
    - гистограмма глубины бронирований
    - помесячное сравнение последних 4 месяцев
    - статистика отмен и возвратов
    - фильтрация по типу номера
    :param request:
    :return:
    """

    today = date.today()
    #Парсинг фильтра по типу номера
    room_type_id = request.GET.get('room_type') or None
    if room_type_id:
        try:
            room_type_id = int(room_type_id)
        except ValueError:
            room_type_id = None

    #Определение периода отчета
    preset = request.GET.get('preset', 'month')
    start_param = request.GET.get('start_date')
    end_param = request.GET.get('end_date')

    if start_param and end_param:
        #Произвольный период с гет параметра
        try:
            start_date = date.fromisoformat(start_param)
            end_date = date.fromisoformat(end_param)
            preset = 'custom'
        except ValueError:
            'Откат текущему месяцу при ошибке'
            start_date = today.replace(day=1)
            end_date = today

    else:
        #Вычисление границ периода по пресету
        if preset == 'prev_month':
            end_date = today.replace(day=1) - timedelta(days=1)
            start_date = end_date.replace(day=1)

        elif preset == 'quarter':
            quarter_start_month = ((today.month -1) // 3) * 3 + 1
            end_date = today
            start_date = today.replace(month = quarter_start_month, day=1)

        elif preset == 'prev_quarter':
            quarter_start_month = ((today.month -1) // 3) * 3 + 1
            end_date = today.replace(month=quarter_start_month, day=1) - timedelta(days=1)
            start_date = end_date.replace(month=((end_date.month - 1) // 3) * 3 + 1, day=1)

        else:
            #Защита от перевернутого диапазона дат
            start_date = today.replace(day=1)
            end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    total_rooms = Room.objects.count() or 1

    #Основные KPI за текущий период
    bookings = list(_bookings_for_period(start_date, end_date, room_type_id))
    revenue = sum((b.total_price for b in bookings), Decimal('0'))
    occ_nights, room_nights, occ_pct = _occ_stats(bookings, start_date, end_date, total_rooms)
    adr = round(revenue / occ_nights, 0) if occ_nights else Decimal('0')
    new_bookings_count = len(bookings)

    #Аналогичный период прошлого года(берем те же даты, но на год раньше)
    py_start = start_date.replace(year=start_date.year - 1)
    py_end = end_date.replace(year=end_date.year - 1)
    py_bookings = list(_bookings_for_period(py_start, py_end, room_type_id))
    py_revenue = sum((b.total_price for b in py_bookings), Decimal('0'))
    py_occ, py_room_nights, py_occ_pct = _occ_stats(py_bookings, py_start, py_end, total_rooms)
    py_adr = round(py_revenue / py_occ, 0) if py_occ else Decimal('0')
    py_new = len(py_bookings)


    def diff_pct(cur, prev):
        #Вычисляет процентное соотношение (cur - prev)/prev *100
        if not prev:
            return None
        return round((float(cur) - float(prev)) / float(prev) * 100, 1)

    def diff_pp(cur, prev):
        #Вычисляет разницу в процентных пунктах (для показателей уже выраженных процентах)
        return round(cur - prev, 1)

    def build_picup(blist):
        """
        Показывает как накапливаются бронирования от 90 дней до заезда до дня заезда
        по оси x дни до заезда, по оси y кол-во бронирований сделанных не позже чем за x дней до заезда
        строится для текущ и прошлогод для стравнения
        :return:
        """
        curve = []
        for days_before in range(90, -1, -1):
            cnt = sum(
                1 for b in blist
                if (b.check_in_date - b.created_at.date()).days >= days_before
            )
            curve.append(cnt)


    picup_cur = build_picup(bookings)
    picup_prev = build_picup(py_bookings)

    picup_labels = [f'-{90-i}' if i < 90 else '0' for i in range(91)]

    #Глубина бронирования
    #Гистограмма(за сколько дней до заезда гости бронируют номера)
    #Разбита на 7 корзин
    depth_buckets = [
        ('0-7', 0, 7),
        ('8-14', 8, 14),
        ('15-30', 15, 30),
        ('31-60', 31, 60),
        ('61-90', 61, 90),
        ('91-180', 91, 180),
        ('180+', 181, 99999),
    ]

    #Для каждого бронирования считаем разницу в днях между датой заезда и датой создания
    depth_data = []
    all_depth = [(b.check_in_date - b.created_at.date()).days for b in bookings if b.created_at]
    for label, lo, hi in depth_buckets:
        cnt = sum(1 for d in all_depth if lo <= d <= hi)
        depth_data.append({'label': label, 'count': cnt})

    #Медиана и максимум глубины бронирования
    sorted_depths = sorted(all_depth)
    if sorted_depths:
        median_depth = sorted_depths[len(sorted_depths) // 2]
        max_depth = max(sorted_depths)
        #Определяем в какую корзину попадает медиана
        median_bucket = '-'
        for label, lo, hi in depth_buckets:
            if lo <= median_depth <= hi:
                median_bucket = label
                break
    else:
        median_bucket = '-'
        max_depth = 0

    #Помесячное сравнение(таблица за последние 4 месяца)
    #Для каждого из 4 посл мес считаем загрузку, выручку и adr
    #Текущий незавешенный месяц считается до сегодняшнего дня

    monthly_table = []
    for i in range(3, -1, -1):
        #вычисляем начало каждого месяца
        ref = today - timedelta(days=30 * i)
        m_start = ref.replace(day=1)
        last_day = monthrange(m_start.year, m_start.month)[1]
        m_end = m_start.replace(day=last_day)
        is_future = m_end > today

        #Для завершенных месяцев берем весь месяц(m_end)
        #Для текущего незавершенного только до сегодня(today)
        #Чтобы не занижать показатели на будующие дни без данных
        m_end_actual = min(m_end, today)
        #Загружаем бронирования пересекающиеся с фактич периодом месяца
        m_books = list(_bookings_for_period(m_start, m_end_actual, room_type_id))
        m_rev = sum((b.total_price for b in m_books), Decimal('0'))
        m_occ, m_rn, m_pct = _occ_stats(m_books, m_start, m_end_actual, total_rooms)
        m_adr = round(m_rev / m_occ, 0) if m_occ else Decimal('0')
        is_cur = (m_start == start_date.replace(day=1) if not is_future else False)

        monthly_table.append({
            'label': _month_label(m_start), #апрель 2026
            'is_current': is_cur, #Выделить строку в шаблоне
            'is_future': is_future, #Месяц еще не завершен
            'occ_pct': m_pct, #Загрузка в %
            'revenue': int(m_rev), #Выручка в руб
            'adr': int(m_adr), #adr в рублях(ср цена за продан ночь)
        })

    #Отмена и возвраты
    #Считаем процент отмен и сумму возвратов за выбранный период
    all_period_bookings = Booking.objects.filter(
        check_in_date__gte = start_date,
        check_in_date__lte = end_date,
    )
    if room_type_id:
        all_period_bookings = all_period_bookings.filter(room__room_type_id=room_type_id)

    total_all = all_period_bookings.count()
    cancelled_qs = all_period_bookings.filter(status='cancelled')
    total_cancelled = cancelled_qs.count()

    #Процент отмен от общешл числа бронирований за период
    cancel_pct = round(total_cancelled / total_all * 100, 1) if total_all else 0

    #Сумма возвратов из платежей со статусом refunded для отмен брон
    refund_sum = Payment.objects.filter(
        booking__in = cancelled_qs, status = 'refunded'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    #Список типов номеров для выпадающего списка
    room_types = RoomType.objects.all()

    context = {
        'title': 'Аналитический отчет',
        'room_types': room_types,
        'selected_room_type': room_type_id,
        'preset': preset,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'period_label': f'{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}',

        'revenue': int(revenue),
        'revenue_diff': diff_pct(revenue, py_revenue),
        'py_revenue': int(py_revenue),
        'occ_pct': occ_pct,
        'occ_diff': diff_pp(occ_pct, py_occ_pct),
        'py_occ_pct': py_occ_pct,
        'adr': int(adr),
        'adr_diff': diff_pct(adr, py_adr),
        'py_adr': int(py_adr),
        'new_bookings': new_bookings_count,
        'new_bookings_diff': diff_pct(new_bookings_count, py_new),
        'py_new': py_new,

        'pickup_labels_json': json.dumps(picup_labels),
        'pickup_cur_json': json.dumps(picup_cur),
        'pickup_prev_json': json.dumps(picup_prev),

        'cur_year': start_date.year,
        'prev_year': py_start.year,
        'depth_json': json.dumps(depth_data),
        'median_bucket': median_bucket,
        'max_depth': max_depth,
        'monthly_table': monthly_table,

        'total_cancelled': total_cancelled,
        'cancel_pct': cancel_pct,
        'refund_sum': int(refund_sum),
    }

    return render(request, template_name='analytics/report.html', context=context)















