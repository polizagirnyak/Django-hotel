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
    bookings = Booking.objects.filter(
        check_in_date__lte = end,
        check_out_date__gte = start,
    ).exclude(status='cancelled').select_related('room', 'room__room_type')
    if room_type_id:
        bookings = bookings.filter(room__room_type_id = room_type_id)
    return bookings


def _occ_stats(bookings, start, end, total_rooms):
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
    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    preset = request.GET.get('preset', 'month')
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
    else:
        if preset == 'prev_month':
            month_end = today.replace(day=1) - timedelta(days=1)
            month_start = month_end.replace(day=1)
        elif preset == 'quarter':
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

    total_rooms = Room.objects.count() or 1
    cur_bookings = list(_bookings_for_period(month_start, month_end))
    prev_bookings = list(_bookings_for_period(prev_month_start, prev_month_end))

    #Выручка
    cur_revenue = sum(b.total_price for b in cur_bookings)
    prev_revenue = sum(b.total_price for b in prev_bookings)
    revenue_diff = round((cur_revenue - prev_revenue) / prev_revenue * 100, 1) if prev_revenue else None

    #Загрузка
    cur_occ, cur_room_nights, cur_occ_pct = _occ_stats(cur_bookings, month_start, month_end, total_rooms)
    prev_occ, prev_room_nights, prev_occ_pct = _occ_stats(prev_bookings, prev_month_start, prev_month_end, total_rooms)
    occ_diff = round(cur_occ_pct - prev_occ_pct, 1)

    #ADR
    cur_adr = round(cur_revenue / cur_occ, 0) if cur_occ else Decimal('0')
    prev_adr = round(prev_revenue / prev_occ, 0) if prev_occ else Decimal('0')
    adr_diff = round((cur_adr - prev_adr) / prev_adr * 100, 1) if prev_adr else None

    #Средняя выручка от 1 номера за определенный период
    cur_revpar = round(cur_revenue / cur_room_nights, 0) if cur_room_nights else Decimal('0')
    prev_revpar = round(prev_revenue / prev_room_nights, 0) if prev_room_nights else Decimal('0')
    revpar_diff = round((cur_revpar - prev_revpar) / prev_revpar * 100, 1) if prev_revpar else None




