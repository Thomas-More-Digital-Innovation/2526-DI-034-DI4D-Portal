from django_ckeditor_5.widgets import CKEditor5Widget
from .models import News
from django import forms

class NewsForm(forms.ModelForm):
    class Meta:
        model = News
        fields = ['title', 'isPublic', 'showAuthor', 'picture', 'description', 'content']
        widgets = {
            'content': CKEditor5Widget()
        }