"""
Retrieval service for semantic search using embeddings
"""
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from django.db.models import Q
from ai_assistant.models import EmbeddedDocument
from ai_assistant.services.embedder import EmbeddingService

logger = logging.getLogger(__name__)


class RetrieverService:
    """Service to retrieve relevant documents using semantic search"""
    
    def __init__(self):
        self.embedder = EmbeddingService()
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score between 0 and 1
        """
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def search(
        self,
        organization,
        query: str,
        content_types: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents using semantic search
        
        Args:
            organization: Organization to search within
            query: Search query text
            content_types: Optional filter for specific content types
            top_k: Number of results to return
            
        Returns:
            List of relevant documents with metadata and similarity scores
        """
        # Create embedding for query
        query_embedding = self.embedder.embed_text(query)
        
        if not query_embedding:
            logger.error("Failed to create query embedding")
            return []
        
        # Get all embedded documents for organization
        filters = Q(organization=organization)
        if content_types:
            filters &= Q(content_type__in=content_types)
        
        embedded_docs = EmbeddedDocument.objects.filter(filters)
        
        # Calculate similarities
        results = []
        for doc in embedded_docs:
            if not doc.embedding:
                continue
            
            similarity = self.cosine_similarity(query_embedding, doc.embedding)
            
            results.append({
                'content_type': doc.content_type,
                'object_id': doc.object_id,
                'content': doc.content,
                'metadata': doc.metadata,
                'similarity': similarity,
            })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]
    
    def search_tickets(self, organization, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search only tickets"""
        return self.search(organization, query, content_types=['ticket'], top_k=top_k)
    
    def search_quotes(self, organization, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search only quotes"""
        return self.search(organization, query, content_types=['quote'], top_k=top_k)
    
    def search_suppliers(self, organization, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search only suppliers"""
        return self.search(organization, query, content_types=['supplier'], top_k=top_k)
    
    def get_context_for_query(self, organization, query: str, max_context_length: int = 4000) -> str:
        """
        Get relevant context for a query, formatted for LLM
        
        Args:
            organization: Organization to search within
            query: User query
            max_context_length: Maximum characters for context
            
        Returns:
            Formatted context string
        """
        results = self.search(organization, query, top_k=10)
        
        context_parts = ["# Relevant Information from Database:\n"]
        current_length = len(context_parts[0])
        
        for result in results:
            # Format result
            part = f"\n## {result['content_type'].title()} (Relevance: {result['similarity']:.2f})\n"
            part += f"{result['content']}\n"
            
            # Check if adding this would exceed max length
            if current_length + len(part) > max_context_length:
                break
            
            context_parts.append(part)
            current_length += len(part)
        
        if len(context_parts) == 1:
            return "No relevant information found in the database."
        
        return "".join(context_parts)
