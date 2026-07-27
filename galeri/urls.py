from django.urls import path
from . import views

urlpatterns = [

    # =======================
    # ADMIN
    # =======================

    path(
        "admin/foto/",
        views.foto_list,
        name="foto_list"
    ),

    path(
        "admin/foto/add/",
        views.add_foto,
        name="add_foto"
    ),

    path(
        "admin/foto/delete/<int:foto_id>/",
        views.delete_foto,
        name="delete_foto"
    ),

    # =======================
    # USER
    # =======================

    path(
        "foto/",
        views.foto_user,
        name="foto"
    ),

    path(
        "hasil/",
        views.hasil,
        name="hasil"
    ),

]