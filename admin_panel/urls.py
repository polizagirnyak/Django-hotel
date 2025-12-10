from django.urls import path
from .views import (room_edit, room_type_edit, room_list,
                    room_create, room_delete, rooms_dashboard,
                    room_type_create, room_type_delete, room_type_list,
                    booking_create_with_customer, booking_list, booking_edit,
                    booking_dashboard, booking_delete, index)
from .views import (customer_edit, customer_list, customer_detail)


urlpatterns = [
    path('', index, name='index'),
    path('room-types/', room_type_list, name='room_type_list'),
    path('room-types/create/', room_type_create, name='room_type_create'),
    path('room-types/<int:pk>/edit/', room_type_edit, name='room_type_edit'),
    path('room-types/<int:pk>/delete/', room_type_delete, name='room_type_delete'),

    path('rooms/', room_list, name='room_list'),
    path('rooms/create/', room_create, name='room_create'),
    path('rooms/<int:pk>/edit/', room_edit, name='room_edit'),
    path('rooms/<int:pk>/delete/', room_delete, name='room_delete'),

    path('rooms-dashboard/', rooms_dashboard, name='rooms_dashboard'),

    path('bookings/create-with-customer/',booking_create_with_customer, name='booking_create_with_customer'),
    path('bookings/<int:pk>/edit/', booking_edit, name='booking_edit'),
    path('booking/<int:pk>/delete/', booking_delete, name='booking_delete'),
    path('bookings/', booking_list, name='booking_list'),
    path('booking-dashboard/', booking_dashboard, name='booking_dashboard'),

    #Клиенты
    path('customers/', customer_list, name='customer_list'),
    path('customers/<int:pk>/edit/', customer_edit, name='customer_edit'),
    path('customers/<int:pk>/', customer_detail, name='customer_detail'),
]