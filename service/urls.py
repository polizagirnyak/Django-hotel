from django.urls import path
from . import views


urlpatterns = [
    path('', views.services_dashboard, name='services_dashboard'),
    path('categories/', views.service_categories, name='service_categories'),
    path('categories/add/', views.service_category_add, name='service_category_add'),
    path('categories/<int:pk>/edit/', views.service_category_edit, name='service_category_edit'),
    path('categories/<int:pk>/delete/', views.service_category_delete, name='service_category_delete'),

    path('list/', views.service_list, name='service_list'),
    path('add/', views.service_add, name='service_add'),
    path('<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('<int:pk>/delete/', views.service_delete, name='service_delete'),

    path('bookings/', views.service_booking_list, name='service_booking_list'),
    path('bookings/add/', views.service_booking_add, name='service_booking_add'),
    path('bookings/<int:pk>/edit/', views.service_booking_edit, name='service_booking_edit'),
    path('bookings/<int:pk>/delete/', views.service_booking_delete, name='service_booking_delete'),
    path('bookings/<int:pk>/change_status/', views.service_booking_change_status, name='service_booking_change_status'),

    path('api/check-service-availability/', views.check_service_availability, name='check_service_availability'),
]