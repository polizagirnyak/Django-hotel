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
            messages.error(request, 'Нельзя удалить ктегорию, в которой есть услуги')
        else:
            category.delete()
            messages.success(request, 'Категория успешно удалена')
            return redirect('service_categories')
    return render(request, template_name='service/category_confirm_delete.html', context={'category':category})




