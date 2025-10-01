from django.db import models
from users.models import User


class Content(models.Model):
    STATUS_CHOICES = (
        ('safe', 'Safe'),
        ('flagged', 'Flagged'),
        ('banned', 'Banned'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contents")
    text = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)  # use auto_now_add, not auto_now
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='safe')

    def __str__(self):
        return f"{self.user.username}: {self.text[:30]}..."


class ModerationResult(models.Model):
    LABEL_CHOICES = (
        ("toxic", "Toxic"),
        ("spam", "Spam"),
        ("fraud", "Fraud"),
        ("drug", "Drug-related"),
        ("harassment", "Harassment"),
        ("safe", "Safe"),
    )
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="moderation_results")
    label = models.CharField(choices=LABEL_CHOICES, max_length=20)
    confidence_score = models.FloatField(default=0.0)
    action = models.CharField(max_length=20, choices=(("allow", "Allow"), ("review", "Review"), ("ban", "Ban")), default="review")

    def __str__(self):
        return f"{self.label} ({self.confidence_score})"


class Feedback(models.Model):
    moderator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedbacks")
    moderation_result = models.ForeignKey(ModerationResult, on_delete=models.CASCADE, related_name="feedbacks")
    decision = models.CharField(max_length=20, choices=(("correct", "Correct"), ("wrong", "Wrong")))
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.moderator.username} on {self.moderation_result.label}"
