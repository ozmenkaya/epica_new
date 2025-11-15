import logging
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ai_assistant.models import Conversation, Message, AIAction
from ai_assistant.services.agent import AIAgent

logger = logging.getLogger(__name__)


def get_current_org(request):
    """Get current organization from request"""
    return getattr(request, 'tenant', None)


@login_required
@require_http_methods(["GET", "POST"])
def chat_view(request):
    """
    Main chat interface view
    
    GET: Display chat UI
    POST: Create new conversation
    """
    organization = get_current_org(request)
    
    if not organization:
        return JsonResponse({
            'success': False,
            'error': 'No organization selected. Please select an organization first.'
        }, status=400)
    
    if request.method == "POST":
        # Create new conversation
        conversation = Conversation.objects.create(
            organization=organization,
            user=request.user,
            title="New Chat"
        )
        return JsonResponse({
            'success': True,
            'conversation_id': conversation.id
        })
    
    # GET: Show chat interface
    conversations = Conversation.objects.filter(
        organization=organization,
        user=request.user
    )[:10]
    
    return render(request, 'ai_assistant/chat.html', {
        'conversations': conversations
    })


@login_required
@require_POST
def send_message(request, conversation_id):
    """
    Send a message in a conversation
    
    POST data:
        message: User message text
    
    Returns:
        JSON with assistant response
    """
    organization = get_current_org(request)
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        organization=organization,
        user=request.user
    )
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty'
            }, status=400)
        
        # Save user message
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=user_message
        )
        
        # Get conversation history
        history = []
        previous_messages = conversation.messages.all()[:10]  # Last 10 messages
        for msg in previous_messages:
            if msg.content != user_message:  # Exclude the message we just added
                history.append({
                    'role': msg.role,
                    'content': msg.content
                })
        
        # Get AI response
        agent = AIAgent(organization, request.user)
        response = agent.chat(user_message, conversation_history=history)
        
        # Save assistant message
        assistant_msg = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response['content'],
            tokens_used=response['tokens_used'],
            function_call=response.get('function_calls')
        )
        
        # Log actions if any
        for func_call in response.get('function_calls', []):
            AIAction.objects.create(
                message=assistant_msg,
                organization=organization,
                user=request.user,
                action_type='data_query',  # Or derive from function name
                status='success',
                input_data={'function': func_call['name']},
                output_data=func_call['result'],
                completed_at=timezone.now()
            )
        
        # Update conversation title if it's the first exchange
        if conversation.messages.count() == 2:  # User + assistant
            conversation.title = user_message[:50]
            conversation.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': assistant_msg.id,
                'content': response['content'],
                'tokens_used': response['tokens_used'],
                'function_calls': response.get('function_calls', [])
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_message: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_conversation(request, conversation_id):
    """
    Get conversation messages
    
    Returns:
        JSON with conversation and messages
    """
    organization = get_current_org(request)
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        organization=organization,
        user=request.user
    )
    
    messages = []
    for msg in conversation.messages.all():
        messages.append({
            'id': msg.id,
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'function_call': msg.function_call
        })
    
    return JsonResponse({
        'success': True,
        'conversation': {
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat()
        },
        'messages': messages
    })


@login_required
@require_http_methods(["DELETE"])
def delete_conversation(request, conversation_id):
    """
    Delete a conversation
    """
    organization = get_current_org(request)
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        organization=organization,
        user=request.user
    )
    
    conversation.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Conversation deleted'
    })


@login_required
@require_http_methods(["POST"])
def message_feedback(request, message_id):
    """
    Submit feedback for an AI assistant message
    """
    try:
        organization = get_current_org(request)
        
        # Get message and verify ownership
        message = get_object_or_404(
            Message,
            id=message_id,
            conversation__organization=organization,
            conversation__user=request.user,
            role='assistant'
        )
        
        # Parse request body
        data = json.loads(request.body)
        feedback = data.get('feedback')
        feedback_comment = data.get('feedback_comment', '')
        
        # Validate feedback type
        if feedback not in ['positive', 'negative']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid feedback type'
            }, status=400)
        
        # Update message feedback
        from django.utils import timezone
        message.feedback = feedback
        message.feedback_comment = feedback_comment
        message.feedback_at = timezone.now()
        message.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Feedback saved'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
