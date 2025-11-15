from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('chat/', views.chat_view, name='chat'),
    path('chat/<int:conversation_id>/', views.get_conversation, name='get_conversation'),
    path('chat/<int:conversation_id>/message/', views.send_message, name='send_message'),
    path('chat/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('message/<int:message_id>/feedback/', views.message_feedback, name='message_feedback'),
]
