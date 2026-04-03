
from django.shortcuts import render
from django.db.models import Q
from datetime import datetime, timedelta
from django.template.loader import render_to_string
from collections import defaultdict
from django.http import JsonResponse, HttpResponse
from django.views import View
import pandas as pd
from pandas import date_range
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import io

from .models import Booking, Room, RoomType, Customer

from .views import _auto_update_statuses

CUSTOMER_COLORS = [
    ('#E74C3C', '#C0392B'),  # красный
    ('#3498DB', '#2980B9'),  # синий
    ('#2ECC71', '#27AE60'),  # зелёный
    ('#F39C12', '#D68910'),  # оранжевый
    ('#9B59B6', '#8E44AD'),  # фиолетовый
    ('#1ABC9C', '#17A589'),  # бирюзовый
    ('#E67E22', '#CA6F1E'),  # тёмно-оранжевый
    ('#34495E', '#2C3E50'),  # тёмно-серый
    ('#E91E63', '#C2185B'),  # розовый
    ('#00BCD4', '#0097A7'),  # голубой
    ('#8BC34A', '#689F38'),  # светло-зелёный
    ('#FF5722', '#E64A19'),  # красно-оранжевый
    ('#607D8B', '#455A64'),  # синевато-серый
    ('#795548', '#5D4037'),  # коричневый
    ('#673AB7', '#512DA8'),  # тёмно-фиолетовый
]

STATUS_SHORT = {
    'confirmed': 'Подтв.',
    'checked_in': 'Заселен',
    'checked_out': 'Выехал',
    'awaiting_payment': 'Ожид.',
    'canceled': 'Отменен'
}

class ChessTableView(View):

    def get(self, request):
        today = datetime.now().date()

        # ── Даты ──────────────────────────────────────────────
        start_str = request.GET.get('start_date', '')
        end_str   = request.GET.get('end_date', '')
        # Если даты не переданы, показываем текущую неделю
        if not start_str and not end_str:
            # Начало недели (понедельник)
            start_date = today
            # Конец недели (воскресенье)
            end_date = start_date + timedelta(days=6)
        else:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else today
            except ValueError:
                start_date = today
            try:
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else start_date + timedelta(days=6)
            except ValueError:
                end_date = start_date + timedelta(days=6)

        # Ограничиваем диапазон 90 днями для производительности
        if (end_date - start_date).days > 90:
            end_date = start_date + timedelta(days=90)

        date_range = []
        cur = start_date
        while cur <= end_date:
            date_range.append(cur)
            cur += timedelta(days=1)

        # ── Параметры фильтрации ──────────────────────────────
        room_type_id  = request.GET.get('room_type', '')
        floor         = request.GET.get('floor', '')
        status_filter = request.GET.get('status', '')
        export_format = request.GET.get('export', '')

        # ── Комнаты ───────────────────────────────────────────
        rooms_qs = Room.objects.select_related('room_type').order_by('floor', 'room_number')
        if room_type_id:
            rooms_qs = rooms_qs.filter(room_type_id=room_type_id)
        if floor:
            rooms_qs = rooms_qs.filter(floor=floor)
        if status_filter:
            rooms_qs = rooms_qs.filter(status=status_filter)
        rooms = list(rooms_qs)

        # ── Бронирования ──────────────────────────────────────
        bookings_qs = Booking.objects.filter(
            check_in_date__lte=end_date,
            check_out_date__gt=start_date,
        ).select_related('customer', 'room', 'room__room_type')

        # Если фильтр по комнатам активен — ограничиваем бронирования
        if rooms_qs.query.where:
            room_ids = [r.id for r in rooms]
            bookings_qs = bookings_qs.filter(room_id__in=room_ids)

        bookings = list(bookings_qs)

        # ── Цвета клиентов ────────────────────────────────────
        customer_colors = {}   # customer_id -> (light_color, dark_color)
        color_idx = 0
        for b in bookings:
            cid = b.customer.id
            if cid not in customer_colors:
                customer_colors[cid] = CUSTOMER_COLORS[color_idx % len(CUSTOMER_COLORS)]
                color_idx += 1

        # ── Плоский список записей для шаблона ────────────────
        # Формат: [{room_id, date_str, ...}, ...]
        # Шаблон Django не умеет делать dict lookup по переменной,
        # поэтому передаём плоский список и итерируем в шаблоне.
# УДАЛИТЬ
        # bookings_list = []
        # for b in bookings:
        #     room_id = b.room.id
        #     light, dark = customer_colors[b.customer.id]
        #     # Определяем пересечение дат бронирования с отображаемым диапазоном
        #     seg_start = max(b.check_in_date, start_date)
        #     seg_end   = min(b.check_out_date - timedelta(days=1), end_date)  # check_out — день выезда, не занят
        #     cur = seg_start
        #     while cur <= seg_end:
        #         bookings_list.append({
        #             'room_id':        room_id,
        #             'date_str':       cur.strftime('%Y-%m-%d'),
        #             'customer_name':  b.customer.get_full_name(),
        #             'customer_last_name': b.customer.last_name,
        #             'color':          light,
        #             'color_dark':     dark,
        #             'check_in':       b.check_in_date,
        #             'check_out':      b.check_out_date,
        #             'status_display': b.get_status_display(),
        #             'status_short':   STATUS_SHORT.get(b.status, b.status),
        #             'total_price':    b.total_price,
        #             'booking_id':     b.id,
        #         })
        #         cur += timedelta(days=1)
        from collections import defaultdict

        schedule_map = defaultdict(dict)
        booking_spans = defaultdict(dict)

        for b in bookings:
            room_id = b.room.id
            light, dark = customer_colors[b.customer.id]

            seg_start = max(b.check_in_date, start_date)
            seg_end = min(b.check_out_date - timedelta(days=1), end_date)

            visible_dates = []
            cur = seg_start
            while cur <= seg_end:
                visible_dates.append(cur)
                cur += timedelta(days=1)

            if not visible_dates:
                continue

            booking_dict = {
                'room_id': room_id,
                'customer_name': b.customer.get_full_name(),
                'customer_last_name': b.customer.last_name,
                'customer_first_name': b.customer.first_name,
                'color': light,
                'color_dark': dark,
                'check_in': b.check_in_date,
                'check_out': b.check_out_date,
                'status_display': b.get_status_display(),
                'status_short': STATUS_SHORT.get(b.status, b.status),
                'total_price': b.total_price,
                'booking_id': b.id,
            }

            for d in visible_dates:
                schedule_map[room_id][d.strftime('%Y-%m-%d')] = booking_dict

            # colspan только для первого видимого дня
            first_date_str = visible_dates[0].strftime('%Y-%m-%d')
            booking_spans[room_id][first_date_str] = len(visible_dates)

        # ── Легенда ───────────────────────────────────────────
        seen_customers = {}
        for b in bookings:
            cid = b.customer.id
            if cid not in seen_customers:
                light, dark = customer_colors[cid]
                seen_customers[cid] = {
                    'name':  b.customer.get_full_name(),
                    'color': light,
                }
        legend_items = list(seen_customers.values())

        # ── Данные для фильтров ───────────────────────────────
        room_types = RoomType.objects.all()
        floors     = Room.objects.order_by('floor').values_list('floor', flat=True).distinct()

        filter_params = {
            'room_type': room_type_id,
            'floor':     floor,
            'status':    status_filter,
        }
# ── Русские названия дней для шаблона ─────────────────
        DAYS_RU_SHORT   = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        MONTHS_RU_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн',
                           'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
        date_range_rich = [
            {
                'date':       d,
                'day':        d.strftime('%d'),
                'dow':        DAYS_RU_SHORT[d.weekday()],
                'mon':        MONTHS_RU_SHORT[d.month - 1],
                'is_weekend': d.weekday() >= 5,
                'date_str':   d.strftime('%Y-%m-%d'),
            }
            for d in date_range
        ]

        context = {
            'rooms':            rooms,
            'date_range':       date_range,
            'date_range_rich':  date_range_rich,
            #'bookings_list':    bookings_list, УДАЛИТЬ
            'schedule_map': dict(schedule_map),  # было: bookings_list
            'booking_spans': dict(booking_spans),  # новое
            'start_date':       start_date,
            'end_date':         end_date,
            'room_types':       room_types,
            'floors':           floors,
            'status_choices':   Room.ROOM_STATUS,
            'customer_colors':  customer_colors,
            'legend_items':     legend_items,
            'filter_params':    filter_params,
        }
        return render(request, 'admin_panel/chess_table.html', context)


