from django.db import models
from django.conf import settings
from accounts.models import Organization


class Conversation(models.Model):
    """Chat conversation for AI assistant"""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ai_conversations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_conversations')
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['organization', '-updated_at']),
            models.Index(fields=['user', '-updated_at']),
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.title or 'Conversation'} - {self.created_at.strftime('%Y-%m-%d')}"


class Message(models.Model):
    """Individual message in conversation"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: store function calls/actions taken
    function_call = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class AIAction(models.Model):
    """Log of actions performed by AI"""
    ACTION_TYPES = [
        ('ticket_update', 'Ticket Update'),
        ('ticket_create', 'Ticket Create'),
        ('quote_request', 'Quote Request'),
        ('email_send', 'Email Send'),
        ('category_create', 'Category Create'),
        ('supplier_update', 'Supplier Update'),
        ('data_query', 'Data Query'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='actions')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ai_actions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_actions')
    
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Store action details
    input_data = models.JSONField()
    output_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.action_type} - {self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class EmbeddedDocument(models.Model):
    """Cache for embedded documents (for vector search)"""
    CONTENT_TYPES = [
        ('ticket', 'Ticket'),
        ('quote', 'Quote'),
        ('supplier', 'Supplier'),
        ('comment', 'Comment'),
        ('email', 'Email'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='embedded_docs')
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    object_id = models.IntegerField()  # ID of the related object
    
    # Text that was embedded
    content = models.TextField()
    
    # Vector embedding (stored as JSON array for now, could use pgvector later)
    embedding = models.JSONField(null=True, blank=True)
    
    # Metadata for search results
    metadata = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['organization', 'content_type']),
            models.Index(fields=['content_type', 'object_id']),
        ]
        unique_together = ['organization', 'content_type', 'object_id']
    
    def __str__(self):
        return f"{self.content_type} #{self.object_id} - {self.organization.name}"
