"""
Action functions that the AI can execute
"""
import logging
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q
from django.utils import timezone
from core.models import Ticket, Quote, Supplier

logger = logging.getLogger(__name__)


def search_tickets(organization, user, query: str, status: str = None, limit: int = 10):
    """
    Search tickets in the organization
    
    Args:
        organization: Organization instance
        user: User instance
        query: Search query
        status: Optional status filter
        limit: Maximum results
        
    Returns:
        Dict with search results
    """
    try:
        # Base queryset - user can only see their own tickets
        tickets = Ticket.objects.filter(
            organization=organization,
            portal_user=user
        )
        
        # Apply status filter
        if status:
            tickets = tickets.filter(status=status)
        
        # Search in title and description
        tickets = tickets.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
        
        # Get results
        tickets = tickets.order_by('-created_at')[:limit]
        
        results = []
        for ticket in tickets:
            results.append({
                'id': ticket.id,
                'title': ticket.title,
                'status': ticket.status,
                'category': ticket.category.name,
                'created_at': ticket.created_at.isoformat(),
                'description': ticket.description[:200]
            })
        
        return {
            'success': True,
            'count': len(results),
            'tickets': results
        }
    except Exception as e:
        logger.error(f"Error in search_tickets: {e}")
        return {'success': False, 'error': str(e)}


def get_ticket_stats(organization, period: str = 'month'):
    """
    Get ticket statistics for organization
    
    Args:
        organization: Organization instance
        period: Time period ('today', 'week', 'month', 'year', 'all')
        
    Returns:
        Dict with statistics
    """
    try:
        # Calculate date range
        now = timezone.now()
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:  # all
            start_date = None
        
        # Base queryset
        tickets = Ticket.objects.filter(organization=organization)
        if start_date:
            tickets = tickets.filter(created_at__gte=start_date)
        
        # Calculate stats
        total_count = tickets.count()
        status_breakdown = tickets.values('status').annotate(count=Count('id'))
        category_breakdown = tickets.values('category__name').annotate(count=Count('id')).order_by('-count')[:5]
        
        return {
            'success': True,
            'period': period,
            'total_tickets': total_count,
            'by_status': {item['status']: item['count'] for item in status_breakdown},
            'top_categories': [
                {'category': item['category__name'], 'count': item['count']}
                for item in category_breakdown
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_ticket_stats: {e}")
        return {'success': False, 'error': str(e)}


def update_ticket_status(organization, user, ticket_id: int, new_status: str):
    """
    Update ticket status
    
    Args:
        organization: Organization instance
        user: User instance
        ticket_id: ID of ticket to update
        new_status: New status value
        
    Returns:
        Dict with result
    """
    try:
        ticket = Ticket.objects.get(
            id=ticket_id,
            organization=organization,
            portal_user=user
        )
        
        old_status = ticket.status
        ticket.status = new_status
        ticket.save()
        
        return {
            'success': True,
            'ticket_id': ticket_id,
            'old_status': old_status,
            'new_status': new_status,
            'message': f'Ticket #{ticket_id} status updated from {old_status} to {new_status}'
        }
    except Ticket.DoesNotExist:
        return {
            'success': False,
            'error': f'Ticket #{ticket_id} not found or you do not have permission to modify it'
        }
    except Exception as e:
        logger.error(f"Error in update_ticket_status: {e}")
        return {'success': False, 'error': str(e)}


def search_suppliers(organization, query: str):
    """
    Search suppliers in the organization
    
    Args:
        organization: Organization instance
        query: Search query
        
    Returns:
        Dict with search results
    """
    try:
        suppliers = Supplier.objects.filter(
            organizations__in=[organization],
            name__icontains=query
        )[:10]
        
        results = []
        for supplier in suppliers:
            categories = [cat.name for cat in supplier.categories.all()]
            results.append({
                'id': supplier.id,
                'name': supplier.name,
                'email': supplier.email or '',
                'phone': supplier.phone or '',
                'categories': categories
            })
        
        return {
            'success': True,
            'count': len(results),
            'suppliers': results
        }
    except Exception as e:
        logger.error(f"Error in search_suppliers: {e}")
        return {'success': False, 'error': str(e)}


def get_supplier_stats(organization):
    """
    Get supplier statistics for organization
    
    Args:
        organization: Organization instance
        
    Returns:
        Dict with statistics
    """
    try:
        suppliers = Supplier.objects.filter(organizations__in=[organization])
        
        total_count = suppliers.count()
        
        # Get category breakdown
        category_stats = {}
        for supplier in suppliers:
            for category in supplier.categories.all():
                if category.name in category_stats:
                    category_stats[category.name] += 1
                else:
                    category_stats[category.name] = 1
        
        return {
            'success': True,
            'total_suppliers': total_count,
            'by_category': category_stats
        }
    except Exception as e:
        logger.error(f"Error in get_supplier_stats: {e}")
        return {'success': False, 'error': str(e)}


def get_quote_stats(organization, period: str = 'month'):
    """
    Get quote statistics for organization
    
    Args:
        organization: Organization instance
        period: Time period ('today', 'week', 'month', 'year', 'all')
        
    Returns:
        Dict with statistics
    """
    try:
        # Calculate date range
        now = timezone.now()
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:  # all
            start_date = None
        
        # Base queryset
        quotes = Quote.objects.filter(ticket__organization=organization)
        if start_date:
            quotes = quotes.filter(created_at__gte=start_date)
        
        # Calculate stats
        total_count = quotes.count()
        
        # Get supplier breakdown
        supplier_breakdown = quotes.values('supplier__name').annotate(count=Count('id')).order_by('-count')[:5]
        
        return {
            'success': True,
            'period': period,
            'total_quotes': total_count,
            'top_suppliers': [
                {'supplier': item['supplier__name'], 'count': item['count']}
                for item in supplier_breakdown
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_quote_stats: {e}")
        return {'success': False, 'error': str(e)}
