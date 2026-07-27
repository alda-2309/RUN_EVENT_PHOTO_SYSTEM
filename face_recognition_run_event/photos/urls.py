from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Halaman Utama (Proses Deteksi dan Pencarian Wajah)
    path('', views.index, name='index'),
    path('test-ai/', views.test_ai, name='test_ai'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)