from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='housekeeping_dashboard'),
    path('cleanings/', views.cleanings_list, name='housekeeping_cleanings'),
]