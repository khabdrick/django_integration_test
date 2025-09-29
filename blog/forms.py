from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'content', 'featured_image', 'status']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 10}),
        }
