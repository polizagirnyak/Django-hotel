from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from datetime import datetime, date, timedelta
from .models import Service, ServiceCategory, ServiceBooking
from admin_panel.models import Customer, Booking
from .forms import ServiceForm, ServiceBookingForm, ServiceCategoryForm
from django.core.paginator import Paginator


#Декоратор для проверки, что пользователь-администратор
def staff_required(view_func):
    return user_passes_test(lambda u: u.is_staff)(view_func)

#Главная панель услуг
@login_required
@staff_required
def services_dashboard(request):
    today = date.today()

    #Статистика
    total_services = Service.objects.count()
    active_services = Service.objects.filter(status = 'available').count()
    today_bookings = ServiceBooking.objects.filter(booking_date = today).count()
    pending_bookings = ServiceBooking.objects.filter(status = 'pending').count()

    #Ближайшие записи
    upcoming_bookings = ServiceBooking.objects.filter(
        booking_date__gte = today).select_related('customer', 'service').order_by('booking_date', 'start_time')[:10]
    context = {
        'total_services': total_services,
        'active_services': active_services,
        'today_bookings': today_bookings,
        'pending_bookings': pending_bookings,
        'upcoming_bookings': upcoming_bookings
    }
    return render(request, template_name='service/dashboard.html', context=context)

#Управление категориями
@login_required
@staff_required
def service_categories(request):
    categories = ServiceCategory.objects.all().order_by('order', 'name')
    return render(request, template_name='service/categories.html', context={'categories':categories})

#Добавление категории
@login_required
@staff_required
def service_category_add(request):
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Категория успешно добавлена')
            return redirect('service_categories')
    else:
        form = ServiceCategoryForm()
    context = {
            'form': form,
            'title': 'Добавить ктегорию'
        }
    return render(request, template_name='service/category_form.html', context=context)

#Редактирование категории
@login_required
@staff_required
def service_category_edit(request, pk):
    category = get_object_or_404(ServiceCategory, pk=pk)
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Категория успешно обновлена')
            return redirect('service_categories')
    else:
        form = ServiceCategoryForm(instance=category)
    context = {
            'form': form,
            'title': 'Редактировать категорию'
        }
    return render(request, template_name='service/category_form.html', context=context)

#Удаление категории
@login_required
@staff_required
def service_category_delete(request, pk):
    category = get_object_or_404(ServiceCategory, pk=pk)
    if request.method == 'POST':
        #Проверяем есть ли услуги в этой категории
        if category.services.exists():
            messages.error(request, 'Нельзя удалить категорию, в которой есть услуги')
        else:
            category.delete()
            messages.success(request, 'Категория успешно удалена')
            return redirect('service_categories')
    return render(request, template_name='service/category_confirm_delete.html', context={'category':category})


@login_required
@staff_required
def service_list(request):
    services = Service.objects.select_related('category').all().order_by('order', 'name')
    #Фильтрация
    category_id = request.GET.get('category')
    if category_id:
        services = services.filter(category_id=category_id)
    status = request.GET.get('status')
    if status:
        services = services.filter(status=status)
    #Поиск
    search_query = request.GET.get('search')
    if search_query:
        services = services.filter(
            Q(name__icontains = search_query) |
            Q(disctiption__icontains = search_query) |
            Q(short_discription__icontains = search_query)
        )
    #Пагинация
    paginator = Paginator(services, 10)
    page = request.GET.get('page')
    services = paginator.get_page(page)
    categories = ServiceCategory.objects.all()
    context = {
        'services': services,
        'categories': categories
    }
    return render(request, 'service/service_list.html', context=context)

@login_required
@staff_required
def service_add(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Услуга {service.name} добавлена')
            return redirect('service_list')
    else:
        form = ServiceForm()
    return render(request, 'service/service_add.html', context={'form':form, 'title':'Добавить услугу'})

@login_required
@staff_required
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Услуга {service.name} обновлена')
            return redirect('service_list')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'service/service_add.html', context={'form':form, 'title': 'Редактировать услугу'})

@login_required
@staff_required
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        #Проверяем, есть ли записи на эту услугу
        if service.booking.exists():
            messages.error(request, 'Нельзя удалить услугу, на которую есть записи')
        else:
            service.delete()
            messages.success(request,'Услуга успешно удалена')
        return redirect('service_list')
    return render(request, 'service/service_confirm_delete.html', context ={'service':service})

#Управление записями на услугу
@login_required
@staff_required
def service_booking_list(request):
    bookings = ServiceBooking.objects.select_related('customer', 'service', 'created_by').all()
    #фильтрация
    date_filter = request.GET.get('date')
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            bookings = bookings.filter(booking_date =filter_date)
        except ValueError:
            pass
    status_filter = request.GET.get('status')
    if status_filter:
        bookings = bookings.filter(status = status_filter)

    service_filter = request.GET.get('service')
    if service_filter:
        bookings = bookings.filter(service_id = service_filter)

    #Поиск по клиенту
    customer_search = request.GET.get('customer')
    if customer_search:
        bookings = bookings.filter(
            Q(customer__first_name__icontains = customer_search)|
            Q(customer__last_name__icontains = customer_search)|
            Q(customer__phone__icontains = customer_search)
        )

    #Пагинация
    paginator = Paginator(bookings,10)
    page = request.GET.get('page')
    bookings = paginator.get_page(page)

    services = Service.objects.all()

    context = {
        'bookings':bookings,
        'services':services,
        'today':date.today()
    }
    return render(request, template_name='service/booking_list.html', context=context)

#Добавление(запись на услугу)
@login_required
@staff_required
def service_booking_add(request):
    if request.method == 'POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.created_by = request.user
            booking.save()

            messages.success(request,'Запись на услугу успешно создана')

            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('service_booking_list')
    else:
        form = ServiceBookingForm()
        #Если передан id клиента
        customer_id = request.GET.get('customer_id')
        if customer_id:
            try:
                customer = Customer.objects.get(pk = customer_id)
                form.fields['customer'].initial = customer
            except Customer.DoesNotExist:
                pass
        #Если передан id услуги
        service_id = request.GET.get('service_id')
        if service_id:
            try:
                service = Service.objects.get(pk = service_id)
                form.fields['service'].initial = service
            except Service.DoesNotExist:
                pass
    return render(request, template_name='service/service_booking_add.html', context={'form':form, 'title':'Добавить запись на услугу'})

#Редактирование услуги
@login_required
@staff_required
def service_booking_edit(request, pk):
    booking = get_object_or_404(ServiceBooking, pk=pk)
    if request.method == 'POST':
        form = ServiceBookingForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(request, 'Запись успешно сохранена')
            return redirect('service_booking_list')
    else:
        form = ServiceBookingForm(instance=booking)
    return render(request, template_name='service/service_booking_add.html', context={'form':form, 'title':'Редактировать запись'})

@login_required
@staff_required
def service_booking_delete(request, pk):
    booking = get_object_or_404(ServiceBooking, pk=pk)
    if request.method == 'POST':
        booking.delete()
        messages.success(request, 'Запись успешно удалена')
        return redirect('service_booking_list')
    return render(request, template_name='service/service_booking_confirm_delete', context={'booking':booking})


#Изменение статуса бронирования
@login_required
@staff_required
def service_booking_change_status(request, pk):
    booking = get_object_or_404(ServiceBooking, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(ServiceBooking.BOOKING_STATUS).keys():
            booking.status = new_status
            booking.save()
            messages.success(request, f'Статус записи изменен на {dict(ServiceBooking.BOOKING_STATUS[new_status])}')
    return redirect('service_booking_list')


#Записи клиентов
@login_required
@staff_required
def customer_service_bookings(request, customer_id):
    customer = get_object_or_404(Customer, pk = customer_id)
    bookings = ServiceBooking.objects.filter(customer=customer).select_related('service').order_by('-booking_date', '-start_time')

    current_booking = Booking.objects.filter(
        customer=customer,
        status__in=['confirmed', 'checked_in']
    ).first()

    context = {
        'bookings':bookings,
        'customer':customer,
        'current_booking':current_booking
    }
    return render(request, template_name='service/customer_bookings.html', context=context)


@login_required
@staff_required
def customer_service_booking_add(request, customer_id):
    customer = get_object_or_404(Customer,pk = customer_id)
    if request.method == 'POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.customer = customer
            booking.created_by = request.user
            booking.save()

            messages.success(request, 'Запись на услугу успешно добавлена')

            return redirect('customer_service_bookings')
    else:
        form = ServiceBookingForm(initial={'customer':customer})

    context = {
        'form':form,
        'customer':customer,
        'title':f'Добавить запись нра услугу для {customer.get_full_name()}'
    }
    return render(request, template_name='service/customer_booking_add.html', context=context)

#Проверка доступности услуги в указанное время
@login_required
def check_service_availability(request):
    service_id = request.GET.get('service_id')
    start_time = request.GET.get('start_time')
    booking_date = request.GET.get('date')

    if not all([service_id, booking_date, start_time]):
        return JsonResponse({'error':'Отсутствуют необходимые параметры'})

    try:
        service = Service.objects.get(pk=service_id)
        #Конвертируем дату и время
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        #Расчитываем время окончания
        start_datetime = datetime.combine(booking_date_obj, start_time_obj)
        end_datetime = start_datetime + timedelta(minutes=service.duration)
        end_time_obj = end_datetime.time()

        #Проверяем пересечение существующих записей
        overlapping_bookings = ServiceBooking.objects.filter(
            service = service,
            booking_date = booking_date_obj,
            status__in = ['confirmed', 'pending', 'in_progress']
        ).filter(
            Q(start_time__lt=end_time_obj, end_time__gt=start_time_obj)
        ).exclude(pk=request.GET.get('exclude_id', None))

        is_available = not overlapping_bookings.exists()

        return JsonResponse(
            {
                'available': is_available,
                'end_time': end_time_obj.strftime('%H:%M'),
                'overlapping_bookings': list(
                    overlapping_bookings.values('id', 'customer__first_name', 'customer__last_name', 'start_time', 'end_time')
                )
            }
        )
    except(Service.DoesNotExist, ValueError) as e:
        return JsonResponse({'error':str(e)}, status=400)










