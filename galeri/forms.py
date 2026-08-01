from django import forms
from config.db import get_event_types

def get_jenis_event_choices():
    """Ambil daftar jenis event dari collection events (Tambah Event Baru)"""
    types = get_event_types()
    if types:
        return [(t, t) for t in types]
    # Fallback kalau belum ada data
    return [
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
    jenis_event = forms.ChoiceField(choices=get_jenis_event_choices)