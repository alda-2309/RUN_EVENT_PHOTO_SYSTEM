from django.db import models

class Event(models.Model):

    EVENT_CHOICES = [
    ('Marathon', 'Marathon'),
    ('Fun Run 5k', 'Fun Run 5k'),
    ('Fun Run 10k', 'Fun Run 10k'),
    ('Trail Run', 'Trail Run'),
    ('Night Run', 'Night Run'),
]

    event_type = models.CharField(
        max_length=100,
        choices=EVENT_CHOICES
    )

    timestamp = models.DateTimeField()

    location = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.event_type} - {self.location}"