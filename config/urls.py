from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [

    path('admin/', admin.site.urls),

    path('accounts/', include('allauth.urls')),


    # DASHBOARD
    path('', include('dashboard.urls')),

    # EVENTS
    path('events/', include('events.urls')),

    # PHOTOS
    path('photos/', include('photos.urls')),

    path('galeri/', include('galeri.urls')),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )