from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [

    # ADMIN — semua admin pake tema dasboart
    path('admin/', include('dashboard.admin_urls')),

    # DASHBOARD — public pages
    path('', include('dashboard.urls')),

    # EVENTS — admin CRUD
    path('events/', include('events.urls')),

    # PHOTOS
    path('photos/', include('photos.urls')),

    # GALERI
    path('galeri/', include('galeri.urls')),

    # USERS — auth
    path('', include('users.urls')),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
