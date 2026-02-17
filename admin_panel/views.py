from datetime import date, timedelta, datetime

from django.db import transaction
from django.db.models import Count, Q, Sum, Max
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from service.models import ServiceBooking
from .models import Room, RoomType, Booking
from .forms import RoomForm, RoomTypeForm, CustomerForm, BookingForm, BookingEditForm, SearchForm
from .models import Room, RoomType, Customer
from django.contrib import messages


def index(request):
    return render(request, template_name='admin_panel/index.html')


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
    rooms = Room.objects.select_related('room_type').all()
    # rooms = Room.objects.all()
    total_rooms = rooms.count()
    available_rooms = rooms.filter(status='available').count()
    occupied_rooms = rooms.filter(status='occupied').count()
    maintenance_rooms = rooms.filter(status='maintenance').count()
    #проверка целостности данных
    problems = []
    for room in rooms.filter(status='occupied'):
        #проверяем активные бронирования на занятость комнат
        active_bookings = Booking.objects.filter(
            room = room,
            status__in = ['checked_in', 'confirmed', 'awaiting_payment'],
            check_in_date__lte = date.today(),
            check_out_date__gte=date.today()
        )
        if not active_bookings.exists():
            problems.append(f'Комната {room.room_number} отмечена как занята, но активного бронирования нет')

    context = {
        'rooms': rooms,
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied_rooms': occupied_rooms,
        'maintenance_rooms': maintenance_rooms,
        'problems': problems
    }

    return render(request,
                  template_name='admin_panel/room_list.html',
                  context=context
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
    available_rooms = Room.objects.none()

    # Получаем параметры из GET запроса
    check_in_date = request.GET.get('check_in')
    check_out_date = request.GET.get('check_out')
    room_id = request.GET.get('room_id')
    customer_id = request.GET.get('customer_id')

    # Инициализируем формы с начальными данными
    customer_form = CustomerForm()
    booking_form = BookingForm()
    new_customer = True

    # Если передан ID существующего клиента через GET
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            customer_form = CustomerForm(instance=customer)
            new_customer = False
        except Customer.DoesNotExist:
            messages.error(request, 'Клиент не найден')

    if check_in_date and check_out_date:
        available_rooms = get_available_rooms(check_in_date, check_out_date)
        booking_form = BookingForm(available_rooms=available_rooms, initial={
            'check_in_date': check_in_date,
            'check_out_date': check_out_date
        })

        # Если передан room_id, выбираем его по умолчанию
        if room_id and available_rooms.filter(id=room_id).exists():
            booking_form = BookingForm(available_rooms=available_rooms, initial={
                'room': room_id,
                'check_in_date': check_in_date,
                'check_out_date': check_out_date
            })

    if request.method == 'POST':
        print(f"DEBUG: POST data = {request.POST}")

        # Определяем тип клиента
        customer_option = request.POST.get('customer_option', 'new')
        customer_id_from_form = request.POST.get('customer_id')

        # Для существующего клиента
        if customer_option == 'existing' and customer_id_from_form:
            try:
                # Получаем клиента из БД
                customer = Customer.objects.get(id=customer_id_from_form)
                new_customer = False

                # Создаем booking_form с данными из POST
                mutable_post = request.POST.copy()

                # Добавляем даты, если их нет
                if check_in_date and 'check_in_date' not in mutable_post:
                    mutable_post['check_in_date'] = check_in_date
                if check_out_date and 'check_out_date' not in mutable_post:
                    mutable_post['check_out_date'] = check_out_date

                # Создаем booking_form
                booking_form = BookingForm(mutable_post, available_rooms=available_rooms)

                # Валидируем только booking_form
                if booking_form.is_valid():
                    try:
                        with transaction.atomic():
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
                        print(f"ERROR: {str(e)}")
                else:
                    print(f"DEBUG: booking_form errors = {booking_form.errors}")
                    # Пересоздаем customer_form с данными клиента для отображения
                    customer_form = CustomerForm(instance=customer)

            except Customer.DoesNotExist:
                messages.error(request, 'Выбранный клиент не найден')
                customer_form = CustomerForm(request.POST)
                new_customer = True

        else:
            # Для нового клиента
            new_customer = True
            customer_form = CustomerForm(request.POST)
            booking_form = BookingForm(request.POST, available_rooms=available_rooms)

            # Проверяем обе формы
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

    # Получаем список клиентов для автозаполнения
    customers = Customer.objects.all()[:50]

    context = {
        'customer_form': customer_form,
        'booking_form': booking_form,
        'available_rooms': available_rooms,
        'check_in_date': check_in_date,
        'check_out_date': check_out_date,
        'today': date.today(),
        'customers': customers,
        'new_customer': new_customer,
    }
    return render(request, 'admin_panel/booking_create_with_customer.html', context)

def search_customers(request):
    #Поиск клиентов для автозаполнения
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'results':[]})
    customers = Customer.objects.filter(
        Q(last_name__icontains=query) |
        Q(phone__icontains=query) |
        Q(email__icontains=query)
    )[:10]

    results = []
    for customer in customers:
        results.append({
            'id': customer.id,
            'text': f'{customer.last_name} {customer.first_name} - {customer.phone}',
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'email': customer.email,
            'phone': customer.phone,
            'passport_number': customer.passport_number,
            'birthday': customer.birthday.strftime('%Y-%m-%d') if customer.birthday else ''
        })
    return JsonResponse({'results':results})

def get_customer_details(request, customer_id):
    try:
        customer = Customer.objects.get(id=customer_id)
        return JsonResponse({
            'success': True,
            'customer': {
                'id': customer.id,
                'first_name': customer.first_name,
                'last_name': customer.last_name,
                'email': customer.email,
                'phone': customer.phone,
                'passport_number': customer.passport_number,
                'birthday': customer.birthday.strftime('%Y-%m-%d') if customer.birthday else ''
            }
        })
    except Customer.DoesNotExist:
        return JsonResponse({'success':False, 'error':'Клиент не найден'}, status=404)


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
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort_by = request.GET.get('sort', '-created_at')

    #Допустимые поля сортировки
    ALLOWED_SORT_FIELDS = {
        'id', '-id',
        'check_in_date', '-check_in_date',
        'check_out_date', '-check_out_date',
        'total_price', '-total_price',
        'status', '-status',
        'created_at', '-created_at',
        'customer__last_name', '-customer__last_name',
        'room__room_number', '-room__room_number'
    }

    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = '-created_at'

    #Базовый запрос
    bookings = Booking.objects.select_related('customer', 'room', 'room__room_type').order_by(sort_by)

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
        elif date_filter == "upcoming":
            bookings = bookings.filter(check_in_date__gte = today)
    #Фильтр по произвольному периоду
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            bookings = bookings.filter(check_in_date__gte=date_from_parsed)
        except ValueError:
            date_from = ''

    if date_from:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            bookings = bookings.filter(check_out_date__lte=date_to_parsed)
        except ValueError:
            date_to = ''

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
                                            status__in=['confirmed', 'awaiting_payment']).count()
    today_checkouts = Booking.objects.filter(check_out_date = date.today(),
                                            status = 'checked_in').count()
    active_bookings = Booking.objects.filter(status__in = ['confirmed', 'awaiting_payment', 'checked_in']).count()

    context = {
        'bookings': bookings,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'total_bookings': total_bookings,
        'today_checkins': today_checkins,
        'today_checkouts': today_checkouts,
        'active_bookings': active_bookings,
        'booking_statuses': Booking.BOOKING_STATUS
    }
    return render(request, 'admin_panel/booking_list.html', context=context)

def booking_edit(request, pk):
    #Редактирование существующего бронирования
    booking = get_object_or_404(Booking, pk = pk )
    old_status = booking.status
    old_room = booking.room

    if request.method == 'POST':
        form = BookingEditForm(request.POST, instance=booking)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_booking = form.save(commit=False)
                    new_status = updated_booking.status
                    new_room = updated_booking.room
                    #Пересчет стоимости при изменении дат или комнаты
                    if any(field in form.changed_data for field in ['check_in_date', 'check_out_date', 'room']):
                        nights = (updated_booking.check_out_date - updated_booking.check_in_date).days
                        total_price = nights*updated_booking.room.room_type.price_per_night
                        updated_booking.total_price = total_price

                    #Если изменилась комната, обноявляем статусы
                    if 'room' in form.changed_data and old_status == 'checked_in':
                        #Старую комнату обсвобождаем, если она была занята
                        old_room.status = 'available'
                        old_room.save()

                    #обновляем статус новой комнаты на основе статуса бронирования
                    if new_status == 'checked_in':
                        new_room.status = 'occupied'
                        new_room.save()
                    elif new_status in ['checked_out', 'cancelled']:
                        # Проверяем нет ли других активных бронирований
                        other_active = Booking.objects.filter(
                            room = new_room,
                            status = 'checked_in'
                        ).exclude(pk=booking.pk).exists()
                        if not other_active:
                            new_room.status = 'available'
                            new_room.save()
                    elif old_status == 'checked_in' and new_status != 'checked_in':
                        # Если убираем заселение, освобождаем комнату
                        other_active = Booking.objects.filter(
                            room=new_room,
                            status='checked_in'
                        ).exclude(pk=booking.pk).exists()
                        if not other_active:
                            new_room.status = 'available'
                            new_room.save()

                        # old_room = Room.objects.get(pk=booking.room.pk)
                        # if booking.status == 'checked_in':
                        #     old_room.status = 'available'
                        #     old_room.save()

                        #Новую комнату помечаем как занятую
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

#####КЛИЕНТЫ#####
def customer_list(request):
    search_query = request.GET.get('search', '')
    customers = Customer.objects.annotate(
        booking_count = Count('booking'),
        total_spent = Sum('booking__total_price'),
        last_booking_date = Max('booking__created_at')
    ).select_related()
    total_bookings = Booking.objects.count()
    #Поиск по клиентам
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(passport_number__icontains=search_query)
        )

    #Статистика
    total_customers = customers.count()
    active_customers = Customer.objects.filter(
        booking__status__in=['confirmed', 'checked_in', 'awaiting_payment']
    ).distinct().count()

    context = {
        'customers': customers,
        'search_query': search_query,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_bookings': total_bookings
    }
    return render(request, template_name='admin_panel/customer_list.html', context=context)


def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    #Получаем все бронирования клиента
    bookings = Booking.objects.filter(customer=customer).select_related(
        'room'
    ).order_by('-created_at')

    #Получаем записи на услуги
    service_bookings = ServiceBooking.objects.filter(customer=customer).select_related('service', 'created_by').order_by('-booking_date', '-start_time')


    #Статистика по клиенту
    total_bookings = bookings.count()
    total_spent = bookings.aggregate(
        total = Sum('total_price'))['total'] or 0
    active_bookings = bookings.filter(
        status__in = ['confirmed', 'checked_in', 'awaiting_payment']
    ).count()

    #Статистика по услугам
    total_service_bookings = service_bookings.count()
    active_service_bookings = service_bookings.filter(
        status__in = ['pending', 'confirmed', 'in_progress']
    ).count()
    total_service_spent = service_bookings.aggregate(total=Sum('total_price'))['total'] or 0
    #Последние 5 записей на услугу
    recent_service_bookings = service_bookings[:5]

    #Последнее бронирование
    last_booking = bookings.first()

    #Предпочтения клиенты(самый частый тип номера)
    favorite_room_type = bookings.values(
        'room__room_type__name',
    ).annotate(
        count = Count('id')
    ).order_by('-count').first()

    #Самая популярная услуга
    favorite_service = service_bookings.values(
        'service__name'
    ).annotate(
        count = Count('id')
    ).order_by('-count').first()

    context = {
        'customer': customer,
        'bookings': bookings,
        'total_bookings': total_bookings,
        'total_spent': total_spent,
        'active_bookings': active_bookings,
        'last_booking': last_booking,
        'favorite_room_type': favorite_room_type,
        'total_service_bookings': total_service_bookings,
        'active_service_bookings': active_service_bookings,
        'total_service_spent': total_service_spent,
        'recent_service_bookings': recent_service_bookings,
        'favorite_service': favorite_service
    }
    return render(request, template_name='admin_panel/customer_detail.html', context=context)


def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request,'Инфомация о клиента успешно обновлена')
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
    context = {
        'form': form,
        'customer': customer
    }
    return render(request, template_name='admin_panel/customer_edit.html', context=context)

def booking_status_update(request, pk, status):
    booking = get_object_or_404(Booking, pk=pk)
    all_status = booking.status
    if request.method == 'POST':
        try:
            with transaction.atomic():
                booking.status = status
                if status == 'checked_in':
                    booking.room.status = 'occupied'
                    booking.room.save()
                elif status in ['checked_out', 'cancelled']:
                    booking.room.status = 'available'
                elif status in ['confirmed', 'awaiting_payment']:
                    pass
                booking.save()
                messages.success(request, f'Статус бронирования #{booking.id} изменен)'
                                          f'Статус комнаты {booking.room.room_number} обновлен')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении статусы: {str(e)}')
    return redirect('booking_list')