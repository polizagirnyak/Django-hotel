from collections import defaultdict
from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render

from .models import Service, ServiceBooking, ServiceCategory, ServiceSpecialist


def staff_required(view_func):
    return user_passes_test(lambda user: user.is_staff)(view_func)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _minutes(value):
    return value.hour * 60 + value.minute


def _css_number(value):
    rounded = round(value, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f'{rounded:.2f}'.rstrip('0').rstrip('.')


def _resolve_target_date(request):
    preset = request.GET.get('preset', 'today')
    today = timezone.localdate()

    if preset == 'today':
        return today, 'today'
    if preset == 'tomorrow':
        return today + timedelta(days=1), 'tomorrow'
    if preset == 'date':
        return _parse_date(request.GET.get('date')) or today, 'date'

    selected_date = _parse_date(request.GET.get('date'))
    if selected_date:
        return selected_date, 'date'
    return today, 'today'


def _display_name(specialist):
    if not specialist:
        return 'Не назначен'
    return specialist.get_short_name()


@method_decorator([login_required, staff_required], name='dispatch')
class ServiceChessTableView(View):
    SLOT_MINUTES = 30
    SLOT_WIDTH = 80
    ROW_HEIGHT = 104
    LABEL_WIDTH = 220
    DAY_START = time(8, 0)
    DAY_END = time(22, 0)

    PALETTE = [
        ('#6366f1', '#eef2ff', '#3730a3'),
        ('#f59e0b', '#fff7ed', '#92400e'),
        ('#22c55e', '#ecfdf5', '#166534'),
        ('#ef4444', '#fef2f2', '#991b1b'),
        ('#06b6d4', '#ecfeff', '#155e75'),
        ('#8b5cf6', '#f5f3ff', '#5b21b6'),
    ]

    def get(self, request):
        target_date, preset = _resolve_target_date(request)
        master_filter = request.GET.get('master', '')
        service_filter = request.GET.get('service', '')
        status_filter = request.GET.get('status', '')

        bookings = ServiceBooking.objects.filter(
            booking_date=target_date,
        ).select_related(
            'customer',
            'service',
            'service__category',
            'specialist',
            'specialist__user',
        )

        if master_filter == 'none':
            bookings = bookings.filter(specialist__isnull=True)
        elif master_filter:
            bookings = bookings.filter(specialist_id=master_filter)

        if service_filter:
            bookings = bookings.filter(service_id=service_filter)

        if status_filter:
            bookings = bookings.filter(status=status_filter)

        bookings = list(bookings.order_by('service__category__order', 'service__order', 'service__name', 'start_time'))
        categories = list(ServiceCategory.objects.filter(is_active=True).order_by('order', 'name'))
        category_colors = self._category_colors(categories)

        start_minute, end_minute = self._time_bounds(bookings)
        time_slots = self._time_slots(start_minute, end_minute)
        rows = self._rows(bookings, category_colors, start_minute)

        active_bookings = [
            booking for booking in bookings
            if booking.status not in ('cancelled', 'no_show')
        ]
        busy_minutes = sum(
            max(0, _minutes(booking.end_time) - _minutes(booking.start_time))
            for booking in active_bookings
            if booking.start_time and booking.end_time
        )

        context = {
            'target_date': target_date,
            'preset': preset,
            'today': timezone.localdate(),
            'tomorrow': timezone.localdate() + timedelta(days=1),
            'rows': rows,
            'time_slots': time_slots,
            'categories': categories,
            'category_colors': category_colors,
            'services': Service.objects.select_related('category').order_by('category__order', 'order', 'name'),
            'masters': ServiceSpecialist.objects.filter(is_active=True).select_related('user').order_by(
                'user__last_name', 'user__first_name', 'user__username'
            ),
            'status_choices': ServiceBooking.BOOKING_STATUS,
            'filters': {
                'master': master_filter,
                'service': service_filter,
                'status': status_filter,
            },
            'total_bookings': len(bookings),
            'busy_hours': busy_minutes // 60,
            'busy_minutes_rest': busy_minutes % 60,
            'masters_count': len(rows),
            'timeline_width': len(time_slots) * self.SLOT_WIDTH,
            'label_width': self.LABEL_WIDTH,
            'slot_width': self.SLOT_WIDTH,
            'row_height': self.ROW_HEIGHT,
            'body_height': sum(row['height'] for row in rows),
        }
        return render(request, 'service/chesstable.html', context)

    def _category_colors(self, categories):
        colors = {}
        for index, category in enumerate(categories):
            colors[category.id] = self.PALETTE[index % len(self.PALETTE)]
        return colors

    def _time_bounds(self, bookings):
        start_minute = _minutes(self.DAY_START)
        end_minute = _minutes(self.DAY_END)

        for booking in bookings:
            if booking.start_time:
                start_minute = min(start_minute, _minutes(booking.start_time))
            if booking.end_time:
                end_minute = max(end_minute, _minutes(booking.end_time))

        start_minute = (start_minute // self.SLOT_MINUTES) * self.SLOT_MINUTES
        end_minute = ((end_minute + self.SLOT_MINUTES - 1) // self.SLOT_MINUTES) * self.SLOT_MINUTES
        return start_minute, end_minute

    def _time_slots(self, start_minute, end_minute):
        slots = []
        current = start_minute
        while current <= end_minute:
            slots.append({
                'label': f'{current // 60:02d}:{current % 60:02d}',
                'left': ((current - start_minute) // self.SLOT_MINUTES) * self.SLOT_WIDTH,
            })
            current += self.SLOT_MINUTES
        return slots

    def _rows(self, bookings, category_colors, start_minute):
        grouped = defaultdict(list)
        services = {}

        for booking in bookings:
            row_key = booking.service_id or 'none'
            grouped[row_key].append(booking)
            if booking.service_id:
                services[row_key] = booking.service

        rows = []
        row_top = 0
        for row_key in grouped.keys():
            service = services.get(row_key)
            row_bookings = sorted(grouped[row_key], key=lambda booking: (booking.start_time, booking.end_time))
            specialist_names = sorted({
                _display_name(booking.specialist)
                for booking in row_bookings
                if booking.specialist_id
            })
            events = []

            for lane_index, booking in enumerate(row_bookings):
                events.append(self._event(
                    booking,
                    category_colors,
                    start_minute,
                    row_top + lane_index * self.ROW_HEIGHT,
                ))

            height = max(1, len(row_bookings)) * self.ROW_HEIGHT
            rows.append({
                'key': row_key,
                'name': service.name if service else 'Услуга не указана',
                'subtitle': ', '.join(specialist_names) if specialist_names else 'Специалист не назначен',
                'top': row_top,
                'height': height,
                'events_count': len(row_bookings),
                'events': events,
            })
            row_top += height
        return rows

    def _event(self, booking, category_colors, start_minute, row_top):
        category_id = booking.service.category_id
        border_color, background_color, text_color = category_colors.get(
            category_id,
            ('#64748b', '#f8fafc', '#334155'),
        )
        start = _minutes(booking.start_time)
        end = _minutes(booking.end_time)
        left = self.LABEL_WIDTH + ((start - start_minute) / self.SLOT_MINUTES) * self.SLOT_WIDTH
        slots_count = ((end - start) / self.SLOT_MINUTES) + 1
        width = max(70, slots_count * self.SLOT_WIDTH - 8)
        customer_name = booking.customer.get_full_name()

        return {
            'booking': booking,
            'customer_name': customer_name,
            'service_name': booking.service.name,
            'specialist_name': _display_name(booking.specialist),
            'time_range': f'{booking.start_time:%H:%M}–{booking.end_time:%H:%M}',
            'left': _css_number(left),
            'top': row_top + 8,
            'width': _css_number(width),
            'background_color': background_color,
            'border_color': border_color,
            'text_color': text_color,
        }
