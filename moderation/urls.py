from django.urls import path
from .views import post_comment_view, my_comments_view, flagged_comments_view, give_feedback_view, review_content_view, quick_review_view

urlpatterns = [
    path('post/', post_comment_view, name='post_comment'),
    path('mine/', my_comments_view, name='my_comments'),
    path('flagged/', flagged_comments_view, name='flagged_comments'),
    path('feedback/<int:result_id>/', give_feedback_view, name='give_feedback'),
    path('review/<int:content_id>/', review_content_view, name='review_content'),
    path('quick-review/<int:content_id>/', quick_review_view, name='quick_review'),
]


