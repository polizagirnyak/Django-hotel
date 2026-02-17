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
        start_str = request.GET.get('start_date')
        end_str = request.GET.get('end_date')
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else today
        except ValueError:
            start_date = today
        try:
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else today
        except ValueError:
            end_date = start_date+timedelta(days=30)
        if end_date < start_date:
            end_date = start_date+timedelta(minutes=30)
        if (end_date-start_date).days > 90:
            end_date = start_date+timedelta(days=30)

        date_range = []
        cur = start_date
        while cur <= end_date:
            date_range.append(cur)
            cur+=timedelta(days=1)

        room_type_id = request.GET.get('room_type', '')
        floor = request.GET.get('floor', '')
        status_filter = request.GET.get('status', '')
        export_format = request.GET.get('export', '')

        # --- Комнаты ----------------------------------
        rooms_qs = Room.objects.select_related('room_type').order_by('floor', 'room_number')
        if room_type_id:
            rooms_qs.filter(room_type_id=room_type_id)
        if floor:
            rooms_qs.filter(floor=floor)
        if status_filter:
            rooms_qs.filter(status=status_filter)
        rooms = list(rooms_qs)


        # ----Бронирования ----------------------------------
        bookings_qs = Booking.objects.filter(
            check_in_date = end_date,
            check_out_date = start_date
        ).select_related('customer', 'room', 'room__room_type')

        #Если фильтр по комнатам активен - ограничиваем бронирование
        if rooms_qs.query.where:
            room_ids = [r.id for r in rooms]
            bookings_qs = bookings_qs.filter(room_id__in=room_ids)
        bookings = list(bookings_qs)




