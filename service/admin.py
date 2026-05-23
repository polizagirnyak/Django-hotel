from django.contrib import admin
from .models import ServiceSpecialist, Service, ServiceBooking, ServiceCategory


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('order', 'name')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'duration', 'status', 'min_booking_hours')
    list_filter = ('is_featured', 'category', 'status')
    search_fields = ('name', 'short_description')
    ordering = ('category__order', 'name', 'order')


@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'service', 'specialist', 'status', 'booking_date', 'start_time', 'end_time')
    list_filter = ('service', 'specialist', 'status', 'booking_date')
    search_fields = ('customer__first_name', 'customer__last_name', 'customer__phone', 'service__name')
    date_hierarchy = 'booking_date'


@admin.register(ServiceSpecialist)
class ServiceSpecialistAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'is_active')
    list_filter = ('is_active', 'services')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__phone')
    filter_horizontal = ('services',)

    def services_list(self, obj):
        return ', '.join(obj.services.values_list('name', flat=True))

    services_list.short_description = 'Услуги'

