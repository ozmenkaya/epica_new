"""
Embedding service for converting documents to vectors
"""
import logging
from typing import List, Dict, Any
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service to create embeddings from text"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
    
    def embed_text(self, text: str) -> List[float]:
        """
        Create embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            return []
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple texts (batch)
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.model
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error creating batch embeddings: {e}")
            return []
    
    def prepare_ticket_text(self, ticket) -> str:
        """
        Prepare ticket data for embedding
        
        Args:
            ticket: Ticket model instance
            
        Returns:
            Formatted text for embedding
        """
        parts = [
            f"Ticket #{ticket.id}",
            f"Category: {ticket.category.name}",
            f"Status: {ticket.get_status_display()}",
            f"Title: {ticket.title}",
            f"Description: {ticket.description}",
        ]
        
        if ticket.solution:
            parts.append(f"Solution: {ticket.solution}")
        
        if ticket.internal_note:
            parts.append(f"Internal Note: {ticket.internal_note}")
        
        return "\n".join(parts)
    
    def prepare_quote_text(self, quote) -> str:
        """
        Prepare quote data for embedding
        
        Args:
            quote: Quote model instance
            
        Returns:
            Formatted text for embedding
        """
        parts = [
            f"Quote #{quote.id}",
            f"Ticket: {quote.ticket.title}",
            f"Supplier: {quote.supplier.name}",
            f"Total: {quote.total_price} {quote.currency}",
        ]
        
        if quote.note:
            parts.append(f"Note: {quote.note}")
        
        # Add quote items
        for item in quote.items.all():
            parts.append(f"Item: {item.product_name} - {item.quantity}x {item.unit_price} {quote.currency}")
        
        return "\n".join(parts)
    
    def prepare_supplier_text(self, supplier) -> str:
        """
        Prepare supplier data for embedding
        
        Args:
            supplier: Supplier model instance
            
        Returns:
            Formatted text for embedding
        """
        parts = [
            f"Supplier: {supplier.name}",
            f"Email: {supplier.email}",
        ]
        
        if supplier.phone:
            parts.append(f"Phone: {supplier.phone}")
        
        if supplier.address:
            parts.append(f"Address: {supplier.address}")
        
        # Add categories
        categories = supplier.categories.all()
        if categories:
            cat_names = ", ".join([cat.name for cat in categories])
            parts.append(f"Categories: {cat_names}")
        
        # Add performance metrics if available
        if hasattr(supplier, 'performance_score'):
            parts.append(f"Performance Score: {supplier.performance_score}")
        
        return "\n".join(parts)
    
    def prepare_comment_text(self, comment) -> str:
        """
        Prepare ticket comment for embedding
        
        Args:
            comment: TicketComment model instance
            
        Returns:
            Formatted text for embedding
        """
        return f"Comment on Ticket #{comment.ticket.id} by {comment.user.email}: {comment.text}"
    
    def prepare_email_text(self, email_reply) -> str:
        """
        Prepare email reply for embedding
        
        Args:
            email_reply: EmailReply model instance
            
        Returns:
            Formatted text for embedding
        """
        parts = [
            f"Email from: {email_reply.from_email}",
            f"Subject: {email_reply.subject}",
            f"Body: {email_reply.body}",
        ]
        
        if email_reply.quote:
            parts.append(f"Related to Quote #{email_reply.quote.id}")
        
        return "\n".join(parts)
