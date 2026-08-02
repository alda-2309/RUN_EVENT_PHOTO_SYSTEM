from django.urls import path
from . import views

urlpatterns = [
    # Admin event management
    path('manage/', views.event_list, name='event_list'),
    path('manage/add/', views.event_add, name='event_add'),
    path('manage/detail/', views.event_detail, name='event_detail'),

    # Public map page
    path('map/', views.event_map_view, name='event_map'),

    # API endpoints for map interactivity
    path('api/points/', views.api_get_points, name='api_get_points'),
    path('api/points/add/', views.api_add_point, name='api_add_point'),
    path('api/points/<str:point_id>/', views.api_update_point, name='api_update_point'),
    path('api/points/<str:point_id>/delete/', views.api_delete_point, name='api_delete_point'),

    # Map point photos — foto per checkpoint
    path('api/points/<str:point_id>/photos/', views.api_get_point_photos, name='api_get_point_photos'),
    path('api/points/<str:point_id>/photos/upload/', views.api_upload_point_photo, name='api_upload_point_photo'),
    path('api/points/<str:point_id>/photos/delete-all/', views.api_delete_point_all_photos, name='api_delete_point_all_photos'),
    path('api/points/<str:point_id>/photos/<str:photo_id>/', views.api_delete_point_photo, name='api_delete_point_photo'),
    path('api/route/', views.api_get_route, name='api_get_route'),
    path('api/route/save/', views.api_save_route, name='api_save_route'),
    path('api/points/reset/', views.api_reset_points, name='api_reset_points'),
]
