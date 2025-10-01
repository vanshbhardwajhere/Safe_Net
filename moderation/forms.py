from django import forms
from .models import Content, Feedback


# ✅ Form for users to post comments
class ContentForm(forms.ModelForm):
    class Meta:
        model = Content
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Write your comment here...",
                    "class": "form-control",
                }
            )
        }


# ✅ Form for moderators to give feedback
class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["decision", "notes"]
        widgets = {
            "decision": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Add optional notes...",
                    "class": "form-control",
                }
            ),
        }
