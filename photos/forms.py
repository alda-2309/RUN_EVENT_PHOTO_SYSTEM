from django import forms

class PhotoForm(forms.Form):
    event_id = forms.IntegerField(widget=forms.HiddenInput())
    image = forms.ImageField()