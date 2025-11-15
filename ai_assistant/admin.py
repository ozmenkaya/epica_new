from django.contrib import admin
from .models import Conversation, Message, AIAction, EmbeddedDocument


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'user', 'title', 'created_at', 'updated_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['title', 'user__email', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'role', 'content_preview', 'tokens_used', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content', 'conversation__title']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


@admin.register(AIAction)
class AIActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'user', 'action_type', 'status', 'created_at']
    list_filter = ['action_type', 'status', 'created_at']
    search_fields = ['user__email', 'organization__name']
    readonly_fields = ['created_at', 'completed_at']


@admin.register(EmbeddedDocument)
class EmbeddedDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'content_type', 'object_id', 'updated_at']
    list_filter = ['content_type', 'organization', 'updated_at']
    search_fields = ['content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
