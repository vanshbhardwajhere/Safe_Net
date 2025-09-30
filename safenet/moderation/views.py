from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
import json
import urllib.request

from .forms import ContentForm, FeedbackForm
from .models import Content, ModerationResult
from dashboard.models import AuditLog


# ✅ User posts a comment
@login_required
def post_comment_view(request):
    if request.method == "POST":
        form = ContentForm(request.POST)
        if form.is_valid():
            content = form.save(commit=False)
            content.user = request.user
            content.save()

            # LLM classification using Gemini with strict JSON + rule-based fallback
            label = 'safe'
            confidence = 0.0
            action = 'allow'

            try:
                api_key = getattr(settings, 'GEMINI_API_KEY', '') or 'REPLACE_ME'
                instruction = (
                    "You are a strict JSON classifier. Given a user comment, return JSON ONLY with keys: "
                    "spam, toxic, fraud, drug, harassment (all booleans) and confidence (0..1). "
                    "Definition hints: spam=unsolicited ads/links/repetition; toxic=insults/profanity/hate/slurs; "
                    "fraud=scams/phishing/impersonation/financial deception; drug=illegal drug dealing/solicitation; "
                    "harassment=threats or targeted abuse. If none, all flags false."
                )
                body = {
                    "contents": [
                        {
                            "parts": [
                                {"text": instruction},
                                {"text": f"Comment: {content.text}"}
                            ]
                        }
                    ],
                    "generationConfig": {"response_mime_type": "application/json"}
                }
                req = urllib.request.Request(
                    url='https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=' + api_key,
                    data=json.dumps(body).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    text_out = (
                        data.get('candidates', [{}])[0]
                        .get('content', {})
                        .get('parts', [{}])[0]
                        .get('text', '{}')
                    )
                    parsed = json.loads(text_out) if text_out.strip().startswith('{') else {}

                    is_spam = bool(parsed.get('spam', False))
                    is_toxic = bool(parsed.get('toxic', False))
                    is_fraud = bool(parsed.get('fraud', False))
                    is_drug = bool(parsed.get('drug', False))
                    is_harassment = bool(parsed.get('harassment', False))
                    confidence = float(parsed.get('confidence', 0.6))

                    if is_toxic:
                        label = 'toxic'
                    elif is_drug:
                        label = 'drug'
                    elif is_fraud:
                        label = 'fraud'
                    elif is_spam:
                        label = 'spam'
                    elif is_harassment:
                        label = 'harassment'
                    else:
                        label = 'safe'

                    action = 'review' if label != 'safe' else 'allow'
            except Exception:
                # Rule-based fallback
                text_lower = content.text.lower()

                profanity = [
                    'fuck', 'shit', 'bitch', 'bastard', 'asshole', 'dick', 'cunt',
                    'motherfucker', 'fucker', 'ass', 'fuk', 'fu*k'
                ]
                drug_keywords = ['cocaine', 'heroin', 'meth', 'weed', 'marijuana', 'ecstasy', 'sell drugs', 'buy drugs']
                fraud_keywords = ['scam', 'phish', 'otp', 'credit card', 'bank details', 'ssn', 'pan number']
                spam_patterns = ['http://', 'https://', 'buy now', 'click here', 'free $$$']

                if any(w in text_lower for w in profanity):
                    label = 'toxic'
                    confidence = 0.9
                    action = 'review'
                elif any(w in text_lower for w in drug_keywords):
                    label = 'drug'
                    confidence = 0.8
                    action = 'review'
                elif any(w in text_lower for w in fraud_keywords):
                    label = 'fraud'
                    confidence = 0.75
                    action = 'review'
                elif any(w in text_lower for w in spam_patterns) or (len(text_lower.split()) <= 2 and text_lower == text_lower.split()[0] * 1):
                    label = 'spam'
                    confidence = 0.7
                    action = 'review'

            result = ModerationResult.objects.create(
                content=content,
                label=label,
                confidence_score=confidence,
                action=action,
            )

            # Only flag when LLM is unsure; otherwise apply LLM decision
            review_threshold = 0.72  # below -> needs moderator review
            ban_threshold = 0.90     # very confident harmful -> auto-ban content

            if label == 'safe':
                if confidence >= review_threshold:
                    content.status = 'safe'
                    result.action = 'allow'
                else:
                    content.status = 'flagged'
                    result.action = 'review'
            else:
                if confidence >= ban_threshold:
                    content.status = 'banned'
                    result.action = 'ban'
                elif confidence >= review_threshold:
                    # accept LLM judgement and hide content without moderator review
                    content.status = 'banned'
                    result.action = 'ban'
                else:
                    content.status = 'flagged'
                    result.action = 'review'
            result.save(update_fields=['action'])
            content.save(update_fields=['status'])

            if content.status == 'flagged':
                messages.warning(request, "Comment submitted and flagged for review ⚠️")
                # Log that a content item was flagged
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='updated_status',
                        content=content,
                        moderation_result=result,
                        notes=f'Auto-flagged by LLM as {label}'
                    )
                except Exception:
                    pass
            else:
                messages.success(request, "Comment posted ✅")
            return redirect("home")
    else:
        form = ContentForm()
    return render(request, "moderation/post_comment.html", {"form": form})


# ✅ Show all comments of the current user
@login_required
def my_comments_view(request):
    comments = Content.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "moderation/my_comments.html", {"comments": comments})


# ✅ Moderator: review flagged comments
@login_required
def flagged_comments_view(request):
    flagged = Content.objects.filter(status="flagged").order_by("-created_at")
    return render(request, "moderation/flagged_comments.html", {"flagged": flagged})


# ✅ Moderator: give feedback on a moderation result
@login_required
def give_feedback_view(request, result_id):
    result = get_object_or_404(ModerationResult, id=result_id)
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.moderator = request.user
            feedback.moderation_result = result
            feedback.save()
            # Audit log
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action='feedback_given',
                    content=result.content,
                    moderation_result=result,
                    notes=feedback.notes or ''
                )
            except Exception:
                pass
            messages.success(request, "Feedback submitted 👍")
            return redirect("flagged_comments")
    else:
        form = FeedbackForm()
    return render(request, "moderation/feedback.html", {"form": form, "result": result})
