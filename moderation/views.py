from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
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
                    "You are a content moderation AI. Analyze the user comment and return JSON ONLY with these keys: "
                    "category (string), confidence (0..1), needs_review (boolean). "
                    "Categories: 'safe', 'toxic', 'spam', 'drug', 'fraud', 'harassment'. "
                    "DRUG DETECTION: Flag as 'drug' if content mentions: drug names (cocaine, heroin, meth, weed, marijuana, ecstasy, LSD, etc.), "
                    "drug dealing/selling, drug use instructions, drug paraphernalia, or drug-related slang. "
                    "Examples of drug-related content: 'white snow' (cocaine), 'green stuff' (marijuana), 'buy drugs', 'sell weed', etc. "
                    "TOXIC: insults, profanity, hate speech, slurs. "
                    "SPAM: ads, links, repetitive content, promotional material. "
                    "FRAUD: scams, phishing, financial deception. "
                    "HARASSMENT: threats, targeted abuse. "
                    "Set needs_review=true if you're uncertain or if content is borderline. "
                    "Return JSON format: {\"category\": \"safe\", \"confidence\": 0.9, \"needs_review\": false}"
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

                    # Get the category and confidence from Gemini
                    label = parsed.get('category', 'safe')
                    confidence = float(parsed.get('confidence', 0.6))
                    needs_review = bool(parsed.get('needs_review', False))

                    # Determine action based on category and confidence
                    if label == 'safe':
                        if needs_review or confidence < 0.7:
                            action = 'review'  # Flag uncertain safe content for human review
                        else:
                            action = 'allow'  # Clearly safe content
                    else:
                        # Harmful content detected
                        if confidence >= 0.8 and not needs_review:
                            action = 'ban'  # High confidence harmful content - auto-ban
                        else:
                            action = 'review'  # Uncertain or low confidence - needs human review
            except Exception:
                # Rule-based fallback when Gemini API fails
                text_lower = content.text.lower()

                # Drug-related keywords (including slang and code words)
                drug_keywords = [
                    'cocaine', 'heroin', 'meth', 'weed', 'marijuana', 'ecstasy', 'lsd', 'mdma',
                    'sell drugs', 'buy drugs', 'white snow', 'green stuff', 'crack', 'speed',
                    'crystal', 'ice', 'blow', 'coke', 'dope', 'grass', 'pot', 'hash', 'acid'
                ]
                
                # Toxic content keywords
                profanity = [
                    'fuck', 'shit', 'bitch', 'bastard', 'asshole', 'dick', 'cunt',
                    'motherfucker', 'fucker', 'ass', 'fuk', 'fu*k'
                ]
                
                # Spam patterns
                spam_patterns = ['http://', 'https://', 'buy now', 'click here', 'free $$$', 'www.']
                
                # Fraud patterns
                fraud_keywords = ['scam', 'phish', 'otp', 'credit card', 'bank details', 'ssn', 'pan number']

                # Check for harmful content
                if any(w in text_lower for w in drug_keywords):
                    label = 'drug'
                    confidence = 0.8
                    action = 'review'
                elif any(w in text_lower for w in profanity):
                    label = 'toxic'
                    confidence = 0.9
                    action = 'review'
                elif any(w in text_lower for w in fraud_keywords):
                    label = 'fraud'
                    confidence = 0.75
                    action = 'review'
                elif any(w in text_lower for w in spam_patterns):
                    label = 'spam'
                    confidence = 0.7
                    action = 'review'
                else:
                    label = 'safe'
                    confidence = 0.6
                    action = 'allow'

            result = ModerationResult.objects.create(
                content=content,
                label=label,
                confidence_score=confidence,
                action=action,
            )

            # Apply the action determined by LLM/fallback logic
            if action == 'allow':
                content.status = 'safe'
            elif action == 'ban':
                content.status = 'banned'
            else:  # action == 'review'
                content.status = 'flagged'
            result.save(update_fields=['action'])
            content.save(update_fields=['status'])

            if content.status == 'flagged':
                messages.warning(request, f"Comment submitted and flagged for review ⚠️ (Detected as: {label})")
                # Log that a content item was flagged
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='updated_status',
                        content=content,
                        moderation_result=result,
                        notes=f'Auto-flagged by LLM as {label} (confidence: {confidence:.2f})'
                    )
                except Exception:
                    pass
            elif content.status == 'banned':
                messages.error(request, f"Comment rejected ❌ (Detected as: {label})")
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


# ✅ Admin/Moderator: Review and approve/reject flagged content
@login_required
def review_content_view(request, content_id):
    content = get_object_or_404(Content, id=content_id)
    
    # Check if user has permission to review (admin or moderator)
    if request.user.role not in ['admin', 'moderator']:
        messages.error(request, "You don't have permission to review content.")
        return redirect("dashboard_home")
    
    if request.method == "POST":
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            content.status = 'safe'
            content.save()
            messages.success(request, "Content approved and made visible.")
            
            # Log the action
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action='reviewed',
                    content=content,
                    notes=f'Approved: {notes}' if notes else 'Approved by moderator'
                )
            except Exception:
                pass
                
        elif action == 'reject':
            content.status = 'banned'
            content.save()
            messages.warning(request, "Content rejected and hidden.")
            
            # Log the action
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action='reviewed',
                    content=content,
                    notes=f'Rejected: {notes}' if notes else 'Rejected by moderator'
                )
            except Exception:
                pass
        
        return redirect("flagged_comments")
    
    # Get the moderation result for this content
    moderation_result = content.moderation_results.first()
    
    return render(request, "moderation/review_content.html", {
        "content": content,
        "moderation_result": moderation_result
    })


# ✅ Admin/Moderator: Quick approve/reject via AJAX
@login_required
def quick_review_view(request, content_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    # Check if user has permission to review
    if request.user.role not in ['admin', 'moderator']:
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    content = get_object_or_404(Content, id=content_id)
    action = request.POST.get('action')
    
    if action == 'approve':
        content.status = 'safe'
        content.save()
        
        # Log the action
        try:
            AuditLog.objects.create(
                user=request.user,
                action='reviewed',
                content=content,
                notes='Quick approved by moderator'
            )
        except Exception:
            pass
            
        return JsonResponse({"status": "approved", "message": "Content approved"})
        
    elif action == 'reject':
        content.status = 'banned'
        content.save()
        
        # Log the action
        try:
            AuditLog.objects.create(
                user=request.user,
                action='reviewed',
                content=content,
                notes='Quick rejected by moderator'
            )
        except Exception:
            pass
            
        return JsonResponse({"status": "rejected", "message": "Content rejected"})
    
    return JsonResponse({"error": "Invalid action"}, status=400)
