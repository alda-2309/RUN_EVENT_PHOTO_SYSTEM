from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def lazy_cari_serupa_blaze(request, photo_id):
    from photos.face_views import cari_serupa_blaze
    return cari_serupa_blaze(request, photo_id)


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

    # CARI SERUPA BLAZEFACE (dipakai template test_ai.html)
    path('cari-serupa/<int:photo_id>/', lazy_cari_serupa_blaze, name='cari_serupa_blaze'),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
