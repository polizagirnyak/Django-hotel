from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from .models import Room, RoomType, Booking
from .forms import RoomForm, RoomTypeForm, CustomerForm, BookingForm, BookingEditForm, SearchForm
from .models import Room, RoomType
from django.contrib import messages


def room_type_create(request):
    if request.method == 'POST':
        form = RoomTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тип номера успешно создан!')
            return redirect('room_type_list')
        else:
            messages.error(request, 'Ошибка при заполнении формы!')
    else:
        form = RoomTypeForm()
    return render(request,
                  template_name='admin_panel/room_type_add.html',
                  context={'form': form,
                           'title': 'Добавить тип номера'}
                  )


def room_type_list(request):
    room_types = RoomType.objects.annotate(
        room_count=Count('room')
    )

    # Расчет статистики
    total_rooms_count = Room.objects.count()

    # Передача в контекст
    context = {
        'title': 'Типы комнат',
        'room_types': room_types,
        'total_rooms_count': total_rooms_count,
    }

    return render(request, 'admin_panel/room_type_list.html', context)


def room_type_edit(request, pk):
    """Редактирование типа комнаты"""
    room_type = get_object_or_404(RoomType, pk=pk)

    if request.method == 'POST':
        form = RoomTypeForm(request.POST, instance=room_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тип комнаты успешно обновлен!')
            return redirect('room_type_list')
    else:
        form = RoomTypeForm(instance=room_type)

    context = {
        'form': form,
        'room_type': room_type,
        'title': f'Редактировать тип комнаты: {room_type.name}'
    }
    return render(request, 'admin_panel/room_type_edit.html', context)


def room_type_delete(request, pk):
    """Удаление типа комнаты"""
    room_type = get_object_or_404(RoomType, pk=pk)

    # Проверяем, есть ли комнаты этого типа
    rooms_count = Room.objects.filter(room_type=room_type).count()

    if request.method == 'POST':
        if rooms_count > 0:
            # Если есть комнаты этого типа, предлагаем выбрать новый тип
            new_room_type_id = request.POST.get('new_room_type')
            if new_room_type_id:
                new_room_type = get_object_or_404(RoomType, pk=new_room_type_id)
                # Обновляем все комнаты на новый тип
                Room.objects.filter(room_type=room_type).update(room_type=new_room_type)
                room_type.delete()
                messages.success(request,
                                 f'Тип комнаты удален. {rooms_count} комнат перемещено в тип: {new_room_type.name}')
            else:
                messages.error(request, 'Необходимо выбрать новый тип для существующих комнат')
                return redirect('room_type_delete', pk=pk)
        else:
            room_type.delete()
            messages.success(request, 'Тип комнаты успешно удален!')

        return redirect('room_type_list')

    # Получаем другие типы комнат для выбора
    other_room_types = RoomType.objects.exclude(pk=room_type.pk)

    context = {
        'object': room_type,
        'rooms_count': rooms_count,
        'other_room_types': other_room_types
    }
    return render(request, 'admin_panel/room_type_confirm_delete.html', context)


def room_create(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Комната успешно создана!')
            return redirect('room_list')
        else:
            messages.error(request, 'Ошибка при заполнении формы!')
    else:
        form = RoomForm()
    return render(request,
                  template_name='admin_panel/room_add.html',
                  context={'form': form,
                           'title': 'Добавить комнату'}
                  )


def room_list(request):
    # rooms = Room.objects.select_related('room_type').all()
    rooms = Room.objects.all()
    return render(request,
                  template_name='admin_panel/room_list.html',
                  context={'title': 'Список комнат',
                           'rooms': rooms}
                  )


def room_edit(request, pk):
    """Редактирование комнаты"""
    room = get_object_or_404(Room, pk=pk)

    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, 'Комната успешно обновлена!')
            return redirect('room_list')
    else:
        form = RoomForm(instance=room)

    context = {
        'form': form,
        'room': room,
        'title': f'Редактировать комнату: {room.room_number}'
    }
    return render(request, 'admin_panel/room_edit.html', context)


def room_delete(request, pk):
    """Удаление комнаты"""
    room = get_object_or_404(Room, pk=pk)
    # Проверяем, есть ли активные бронирования
    active_bookings = Booking.objects.filter(
        room=room,
        status__in=['confirmed', 'checked_in', 'awaiting_payment']
    ).exists()

    if request.method == 'POST':
        if active_bookings:
            messages.error(request, 'Нельзя удалить комнату с активными бронированиями!')
            return redirect('room_list')
        room.delete()
        messages.success(request, 'Комната успешно удалена!')
        return redirect('room_list')
    context = {
        'object': room,
        'active_bookings': active_bookings
    }
    return render(request, 'admin_panel/room_confirm_delete.html', context)


def rooms_dashboard(request):
    # Статистика для типов номеров
    room_types_count = RoomType.objects.count()
    room_types = RoomType.objects.all()

    # Расчет средней цены
    avg_price = None
    if room_types_count > 0:
        total_price = sum(rt.price_per_night for rt in room_types)
        avg_price = total_price / room_types_count

    # Статистика для номеров
    total_rooms = Room.objects.count()
    available_rooms = Room.objects.filter(status='available').count()

    context = {
        'title': 'Управление номерами',
        'room_types_count': room_types_count,
        'avg_price': avg_price,
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
    }

    return render(request, 'admin_panel/rooms_dashboard.html', context)


def booking_create_with_customer(request):
    customer_form = CustomerForm(request.POST or None)
    booking_form = BookingForm(request.POST or None)
    available_rooms = Room.objects.none()

    # Получаем параметры из GET запроса
    check_in_date = request.GET.get('check_in')
    check_out_date = request.GET.get('check_out')
    room_id = request.GET.get('room_id')

    if check_in_date and check_out_date:
        available_rooms = get_available_rooms(check_in_date, check_out_date)
        booking_form = BookingForm(available_rooms=available_rooms)

        # Если передан room_id, выбираем его по умолчанию
        if room_id and available_rooms.filter(id=room_id).exists():
            booking_form = BookingForm(available_rooms=available_rooms, initial={'room': room_id})

    if request.method == 'POST':
        customer_form = CustomerForm(request.POST)
        booking_form = BookingForm(request.POST, available_rooms=available_rooms)

        if customer_form.is_valid() and booking_form.is_valid():
            try:
                with transaction.atomic():
                    # Сохраняем клиента
                    customer = customer_form.save()

                    # Сохраняем бронирование
                    booking = booking_form.save(commit=False)
                    booking.customer = customer

                    # Расчет общей стоимости
                    nights = (booking.check_out_date - booking.check_in_date).days
                    total_price = nights * booking.room.room_type.price_per_night
                    booking.total_price = total_price

                    booking.save()

                    # Обновляем статус комнаты
                    booking.room.status = 'occupied'
                    booking.room.save()

                    messages.success(
                        request,
                        f'Бронирование успешно создано! Стоимость: {total_price} руб.'
                    )
                    return redirect('booking_list')

            except Exception as e:
                messages.error(request, f'Ошибка при создании бронирования: {str(e)}')

    context = {
        'customer_form': customer_form,
        'booking_form': booking_form,
        'available_rooms': available_rooms,
        'check_in_date': check_in_date,
        'check_out_date': check_out_date,
        'today': date.today(),
    }
    return render(request, 'admin_panel/booking_create_with_customer.html', context)


def get_available_rooms(check_in_date, check_out_date):
    """Функция для поиска свободных номеров на указанные даты"""
    try:
        check_in = date.fromisoformat(check_in_date) if isinstance(check_in_date, str) else check_in_date
        check_out = date.fromisoformat(check_out_date) if isinstance(check_out_date, str) else check_out_date

        # Находим занятые комнаты в указанный период
        occupied_rooms = Booking.objects.filter(
            Q(check_in_date__lt=check_out) & Q(check_out_date__gt=check_in) &
            Q(status__in=['confirmed', 'checked_in', 'awaiting_payment'])
        ).values_list('room_id', flat=True)

        # Ищем свободные комнаты
        available_rooms = Room.objects.filter(
            status='available'
        ).exclude(
            id__in=occupied_rooms
        ).select_related('room_type')

        return available_rooms

    except (ValueError, TypeError):
        return Room.objects.none()


def booking_list(request):
    #Получаем параметры фильтрации
    status_filter = request.GET.get('status','')
    date_filter = request.GET.get('date','')
    search_query = request.GET.get('search','')

    #Базовый запрос
    bookings = Booking.objects.select_related('customer', 'room', 'room__room_type').order_by('-created_at')

    #Применяем фильтры
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    if date_filter:
        today = date.today()
        if date_filter == 'today':
            bookings = bookings.filter(check_in_date = today)
        elif date_filter == 'tomorrow':
            tomorrow = today + timedelta(days=1)
            bookings = bookings.filter(check_in_date = tomorrow)
        elif date_filter == 'this_week':
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            bookings = bookings.filter(
                Q(check_in_date__range = [start_week, end_week]) |
                Q(check_out_date__range = [start_week, end_week])
            )
        elif date_filter == "upcomming":
            bookings = bookings.filter(check_in_date__gte = today)
    if search_query:
        bookings = bookings.filter(
            Q(customer__first_name__icontains = search_query) |
            Q(customer__last_name__icontains = search_query) |
            Q(room__room_number__icontains=search_query) |
            Q(customer__phone__icontains=search_query)
        )

    #Статистика для карточек
    total_bookings = Booking.objects.count()
    today_checkins = Booking.objects.filter(check_in_date = date.today(),
                                            status__in=['comfirmed', 'awaiting_payment']).count()
    today_checkouts = Booking.objects.filter(check_out_date = date.today(),
                                            status = 'checked_in').count()
    active_bookings = Booking.objects.filter(status__in = ['comfirmed', 'awaiting_payment', 'checked_in']).count()

    context = {
        'bookings': bookings,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'search_query': search_query,
        'total_bookings': total_bookings,
        'today_checkins': today_checkins,
        'today_checkouts': today_checkouts,
        'active_bookings': active_bookings
    }
    return render(request, 'admin_panel/booking_list.html', context=context)

def booking_edit(request, pk):
    #Редактирование существующего бронирования
    booking = get_object_or_404(Booking, pk = pk )
    if request.method == 'POST':
        form = BookingEditForm(request.POST, instance=booking)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_booking = form.save(commit=False)
                    #Пересчет стоимости при изменении дат или комнаты
                    if any(field in form.changed_data for field in ['check_in_date', 'check_out_date', 'room']):
                        nights = (updated_booking.check_out_date - updated_booking.check_in_date).days
                        total_price = nights*updated_booking.room.room_type.price_per_night
                        updated_booking.total_price = total_price
                    #Если изменилась комната, обноявляем статусы
                    if 'room' in form.changed_data:
                        #Старую комнату обсвобождаем, если она была занята
                        old_room = Room.objects.get(pk=booking.room.pk)
                        if booking.status == 'checked_in':
                            old_room.status = 'available'
                            old_room.save()
                        #Новую комнату помечаем как занятую
                        if updated_booking.status == 'checked_in':
                            updated_booking.room.status = 'occupied'
                            updated_booking.room.save()
                    updated_booking.save()
                    messages.success(request, 'Бронироввание успешно обновлено')
                    return redirect('booking_list')
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении бонирования {str(e)}')
    else:
        form = BookingEditForm(instance=booking)
    context = {
        'form': form,
        'booking': booking
    }
    return render(request, 'admin_panel/booking_edit.html', context=context)


def booking_dashboard(request):
    today = date.today()
    #Статистика бронирований
    total_bookings = Booking.objects.count()
    active_bookings = Booking.objects.filter(status__in = ['confirmed', 'checked_in', 'awaiting_payment']).count()

    #Бронирования на сегодня
    today_checkins = Booking.objects.filter(status__in = ['confirmed', 'awaiting_payment'], check_in_date = today).count()
    today_checkouts = Booking.objects.filter(status = 'checked_in', check_out_date = today).count()

    #Предстоящие бронирования(7дней)
    upcoming_checkins = Booking.objects.filter(
        check_in_date__range = [today, today+timedelta(days=7)],
        status__in = ['confirmed', 'awaiting_payment']
    ).count()

    #Статистика по статусам
    status_stats = Booking.objects.values('status').annotate(count=Count('id')).order_by('status')

    #Последние бронирования
    recent_bookings = Booking.objects.select_related('customer', 'room', 'room__room_type').order_by('-created_at')[:5]

    #Бронирования, требующие внимания
    attention_bookings = Booking.objects.filter(
        Q(status='awaiting_payment')|
        Q(check_in_date=today, status='confirmed')
    ).select_related('customer', 'room')[:3]
    context = {
        'total_bookings':total_bookings,
        'active_bookings':active_bookings,
        'today_checkins':today_checkins,
        'today_checkouts':today_checkouts,
        'upcoming_checkins':upcoming_checkins,
        'status_stats':status_stats,
        'recent_bookings':recent_bookings,
        'attention_bookings':attention_bookings,
        'today':today
    }
    return render(request, 'admin_panel/booking_dashboard.html', context=context)

def booking_delete(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        #Освобождаем комнату, если она была занята
        if booking.status == 'checked_in':
            booking.room.status = 'available'
            booking.room.save()
        booking.delete()
        messages.success(request, 'Бронирование успешно удалено')
        return redirect('booking_list')
    return render(request, 'admin_panel/confirm_delete.html', context={'object':booking})
