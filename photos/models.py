from django.db import models
from events.models import Event

class Photo(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE
    )

    image = models.ImageField(
        upload_to='photos/'
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.event.event_type} - {self.uploaded_at}"