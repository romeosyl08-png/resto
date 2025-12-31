from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.meal_llist, name='meal_list'),
    path('meal/<slug:slug>/', views.meal_detail, name='meal_detail'),
]


"""

urlpatterns = [
    path('', views.meal_list, name='meal_list'),
    path('category/<slug:category_slug>/', views.meal_list, name='meal_list_by_category'),
    path('meal/<slug:slug>/', views.meal_detail, name='meal_detail'),
]

"""
