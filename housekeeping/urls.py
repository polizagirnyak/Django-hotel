from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='housekeeping_dashboard'),
    path('cleanings/', views.cleanings_list, name='housekeeping_cleanings'),
    path('assign-cleaning', views.assign_cleaning, name='housekeeping_assign_cleaning'),
    path('assign-repair', views.assign_repair, name='housekeeping_assign_repair'),
    path('rooms/<int:room_id>/state/', views.update_room_state, name='housekeeping_update_state'),
    path('tasks/<int:task_id>/assign/', views.assign_housekeeper, name='housekeeping_assign_housekeeper'),
    path('tasks/<int:task_id>/delete/', views.delete_task, name='housekeeping_delete_task'),
    path('tasks/<int:task_id>/state/', views.update_task_state, name='housekeeping_update_task_state'),
]