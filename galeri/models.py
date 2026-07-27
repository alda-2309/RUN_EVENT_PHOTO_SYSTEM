from django.db import models
from django.contrib.auth.models import User


class Event(models.Model):

    JENIS_EVENT = [
    ('Marathon', 'Marathon'),
    ('Fun Run 5k', 'Fun Run 5k'),
    ('Fun Run 10k', 'Fun Run 10k'),
    ('Trail Run', 'Trail Run'),
    ('Night Run', 'Night Run'),
]

    nama_event = models.CharField(max_length=100)

    jenis_event = models.CharField(
        max_length=20,
        choices=JENIS_EVENT,
        default='Marathon'
    )

    lokasi = models.CharField(max_length=100)

    tanggal_event = models.DateField()

    def __str__(self):
        return self.nama_event


class Foto(models.Model):

    JENIS_EVENT = [
    ('Marathon', 'Marathon'),
    ('Fun Run 5k', 'Fun Run 5k'),
    ('Fun Run 10k', 'Fun Run 10k'),
    ('Trail Run', 'Trail Run'),
    ('Night Run', 'Night Run'),
]
    nama_event = models.CharField(max_length=100)

    gambar = models.ImageField(upload_to='foto/')

    timestamp = models.DateTimeField()

    jenis_event = models.CharField(
        max_length=20,
        choices=JENIS_EVENT,
        default='Marathon'
    )

    def __str__(self):
        return f"{self.nama_event} - {self.jenis_event}"