from django.urls import path
from .views import event_list, event_add, event_detail
from . import views

urlpatterns = [

    # LIST EVENT
    path('', event_list, name='event_list'),

    # TAMBAH EVENT
    path('add/', event_add, name='event_add'),

    # DETAIL EVENT
    path(
        'detail/',
        event_detail,
        name='event_detail'
    ),

]