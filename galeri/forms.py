from django import forms

JENIS_EVENT = [
    ('Marathon', 'Marathon'),
    ('Fun Run 5k', 'Fun Run 5k'),
    ('Fun Run 10k', 'Fun Run 10k'),
    ('Trail Run', 'Trail Run'),
    ('Night Run', 'Night Run'),
]


class FotoForm(forms.Form):
    nama_event = forms.CharField(max_length=100)
    gambar = forms.ImageField()
    timestamp = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    jenis_event = forms.ChoiceField(choices=JENIS_EVENT)