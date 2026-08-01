from django import forms

EVENT_CHOICES = [
    ('Marathon', 'Marathon'),
    ('Fun Run 5k', 'Fun Run 5k'),
    ('Fun Run 10k', 'Fun Run 10k'),
    ('Trail Run', 'Trail Run'),
    ('Night Run', 'Night Run'),
]


class EventForm(forms.Form):
    event_type = forms.ChoiceField(choices=EVENT_CHOICES)
    timestamp = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%d %H:%M')
    )
    location = forms.CharField(max_length=200)