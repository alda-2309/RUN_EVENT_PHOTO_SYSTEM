from django.urls import path
from . import views

urlpatterns = [

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