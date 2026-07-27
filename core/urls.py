from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from photos import views as photos_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('photos.urls')),
    path('cari-serupa/<int:photo_id>/', photos_views.cari_serupa, name='cari_serupa'),
    path('ganti-halaman/', photos_views.ganti_halaman, name='ganti_halaman'),
    path('demo-crop-manual/', photos_views.demo_crop_manual, name='demo_crop_manual'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)