"""
Management command to calculate supplier and customer metrics.
Run daily via cron: python manage.py calculate_metrics
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Q, F, Sum
from django.utils import timezone
from decimal import Decimal
from accounts.models import Organization
from core.models import Supplier, Customer, Quote, Ticket, SupplierMetrics, CustomerMetrics, CustomerFeedback, OwnerReview
from billing.models import Order


class Command(BaseCommand):
	help = 'Calculate and update supplier and customer metrics'

	def add_arguments(self, parser):
		parser.add_argument(
			'--org',
			type=int,
			help='Calculate metrics only for specific organization ID',
		)
		parser.add_argument(
			'--supplier',
			type=int,
			help='Calculate metrics only for specific supplier ID',
		)
		parser.add_argument(
			'--customer',
			type=int,
			help='Calculate metrics only for specific customer ID',
		)

	def handle(self, *args, **options):
		org_id = options.get('org')
		supplier_id = options.get('supplier')
		customer_id = options.get('customer')

		if supplier_id:
			self.calculate_supplier_metrics(supplier_id=supplier_id)
		elif customer_id:
			self.calculate_customer_metrics(customer_id=customer_id)
		else:
			# Calculate for all organizations
			orgs = Organization.objects.all()
			if org_id:
				orgs = orgs.filter(id=org_id)
			
			for org in orgs:
				self.stdout.write(f"\n{'='*60}")
				self.stdout.write(f"Processing organization: {org.name}")
				self.stdout.write(f"{'='*60}")
				
				# Calculate supplier metrics
				suppliers = Supplier.objects.filter(organizations=org)
				self.stdout.write(f"\nCalculating metrics for {suppliers.count()} suppliers...")
				for supplier in suppliers:
					self.calculate_supplier_metrics(supplier.id, org.id)
				
				# Calculate customer metrics
				customers = Customer.objects.filter(organization=org)
				self.stdout.write(f"\nCalculating metrics for {customers.count()} customers...")
				for customer in customers:
					self.calculate_customer_metrics(customer.id, org.id)
			
			self.stdout.write(self.style.SUCCESS("\n✅ All metrics calculated successfully!"))

	def calculate_supplier_metrics(self, supplier_id, org_id=None):
		"""Calculate and update metrics for a single supplier."""
		try:
			supplier = Supplier.objects.get(id=supplier_id)
			
			# Get or create metrics for each organization
			organizations = supplier.organizations.all()
			if org_id:
				organizations = organizations.filter(id=org_id)
			
			for org in organizations:
				metrics, created = SupplierMetrics.objects.get_or_create(
					supplier=supplier,
					organization=org
				)
				
				# 1. Quote metrics
				quotes = Quote.objects.filter(supplier=supplier, ticket__organization=org)
				metrics.total_quotes_sent = quotes.count()
				
				# Accepted quotes (where ticket.selected_quote = this quote)
				accepted = quotes.filter(ticket__selected_quote=F('id'))
				metrics.total_quotes_accepted = accepted.count()
				
				if metrics.total_quotes_sent > 0:
					metrics.win_rate_percent = Decimal(metrics.total_quotes_accepted) / Decimal(metrics.total_quotes_sent) * Decimal('100.00')
				else:
					metrics.win_rate_percent = Decimal('0.00')
				
				# Average quote response time (from ticket creation to quote creation)
				# We'll use created_at times as proxy for now
				quote_times = []
				for quote in quotes.select_related('ticket'):
					delta = quote.created_at - quote.ticket.created_at
					hours = Decimal(str(delta.total_seconds() / 3600))
					quote_times.append(hours)
				
				if quote_times:
					metrics.avg_quote_response_hours = sum(quote_times) / len(quote_times)
				else:
					metrics.avg_quote_response_hours = Decimal('0.00')
				
				# 2. Order metrics
				orders = Order.objects.filter(supplier=supplier, organization=org)
				metrics.total_orders = orders.count()
				metrics.completed_orders = orders.filter(status='completed').count()
				
				# On-time delivery calculation
				on_time = orders.filter(
					status='completed',
					estimated_delivery_date__isnull=False,
					actual_delivery_date__isnull=False,
					actual_delivery_date__lte=F('estimated_delivery_date')
				).count()
				metrics.on_time_deliveries = on_time
				
				if metrics.completed_orders > 0:
					metrics.on_time_delivery_percent = Decimal(on_time) / Decimal(metrics.completed_orders) * Decimal('100.00')
				else:
					metrics.on_time_delivery_percent = Decimal('0.00')
				
				# 3. Customer feedback averages
				feedbacks = CustomerFeedback.objects.filter(supplier=supplier, organization=org)
				metrics.total_feedback_count = feedbacks.count()
				
				if metrics.total_feedback_count > 0:
					avg_data = feedbacks.aggregate(
						avg_quality=Avg('product_quality'),
						avg_comm=Avg('communication'),
						avg_delivery=Avg('delivery_time'),
						avg_overall=Avg('overall_satisfaction')
					)
					metrics.avg_product_quality = Decimal(str(avg_data['avg_quality'] or 0))
					metrics.avg_communication = Decimal(str(avg_data['avg_comm'] or 0))
					metrics.avg_delivery_rating = Decimal(str(avg_data['avg_delivery'] or 0))
					metrics.avg_overall_satisfaction = Decimal(str(avg_data['avg_overall'] or 0))
				else:
					metrics.avg_product_quality = Decimal('0.00')
					metrics.avg_communication = Decimal('0.00')
					metrics.avg_delivery_rating = Decimal('0.00')
					metrics.avg_overall_satisfaction = Decimal('0.00')
				
				# 4. Owner review average
				reviews = OwnerReview.objects.filter(supplier=supplier, organization=org)
				metrics.owner_review_count = reviews.count()
				
				if metrics.owner_review_count > 0:
					avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
					metrics.avg_owner_rating = Decimal(str(avg_rating or 0))
				else:
					metrics.avg_owner_rating = Decimal('0.00')
				
				# 5. Calculate overall score
				metrics.calculate_score()
				metrics.save()
				
				action = "Created" if created else "Updated"
				self.stdout.write(
					f"  {action} metrics for {supplier.name}: Score = {metrics.overall_score:.2f}/100"
				)
		
		except Supplier.DoesNotExist:
			self.stdout.write(self.style.ERROR(f"Supplier with ID {supplier_id} not found"))
		except Exception as e:
			self.stdout.write(self.style.ERROR(f"Error calculating supplier {supplier_id}: {str(e)}"))

	def calculate_customer_metrics(self, customer_id, org_id=None):
		"""Calculate and update metrics for a single customer."""
		try:
			customer = Customer.objects.get(id=customer_id)
			org = customer.organization
			
			if org_id and org.id != org_id:
				return  # Skip if not the requested org
			
			metrics, created = CustomerMetrics.objects.get_or_create(
				customer=customer,
				organization=org
			)
			
			# 1. Ticket and order metrics
			tickets = Ticket.objects.filter(customer=customer, organization=org)
			metrics.total_tickets_created = tickets.count()
			
			orders = Order.objects.filter(ticket__customer=customer, organization=org)
			metrics.total_orders_placed = orders.count()
			
			if metrics.total_tickets_created > 0:
				metrics.conversion_rate_percent = Decimal(metrics.total_orders_placed) / Decimal(metrics.total_tickets_created) * Decimal('100.00')
			else:
				metrics.conversion_rate_percent = Decimal('0.00')
			
			# 2. Response time (from ticket offered to order placed)
			response_times = []
			for order in orders.select_related('ticket'):
				if order.ticket.status == 'accepted' and order.ticket.offered_price:
					# Calculate time from ticket creation to order creation
					delta = order.created_at - order.ticket.created_at
					hours = Decimal(str(delta.total_seconds() / 3600))
					response_times.append(hours)
			
			if response_times:
				metrics.avg_response_time_hours = sum(response_times) / len(response_times)
			else:
				metrics.avg_response_time_hours = Decimal('0.00')
			
			# 3. Cancellation rate
			cancelled = orders.filter(status='cancelled').count()
			metrics.cancelled_orders = cancelled
			
			if metrics.total_orders_placed > 0:
				metrics.cancellation_rate_percent = Decimal(cancelled) / Decimal(metrics.total_orders_placed) * Decimal('100.00')
			else:
				metrics.cancellation_rate_percent = Decimal('0.00')
			
			# 4. Spending
			spending_data = orders.exclude(status='cancelled').aggregate(total=Sum('total'))
			metrics.total_spent = Decimal(str(spending_data['total'] or 0))
			
			completed_orders = orders.exclude(status='cancelled').count()
			if completed_orders > 0:
				metrics.avg_order_value = metrics.total_spent / Decimal(completed_orders)
			else:
				metrics.avg_order_value = Decimal('0.00')
			
			# 5. Owner review average
			reviews = OwnerReview.objects.filter(customer=customer, organization=org)
			metrics.owner_review_count = reviews.count()
			
			if metrics.owner_review_count > 0:
				avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
				metrics.avg_owner_rating = Decimal(str(avg_rating or 0))
			else:
				metrics.avg_owner_rating = Decimal('0.00')
			
			# 6. Calculate overall score
			metrics.calculate_score()
			metrics.save()
			
			action = "Created" if created else "Updated"
			self.stdout.write(
				f"  {action} metrics for {customer.name}: Score = {metrics.overall_score:.2f}/100"
			)
		
		except Customer.DoesNotExist:
			self.stdout.write(self.style.ERROR(f"Customer with ID {customer_id} not found"))
		except Exception as e:
			self.stdout.write(self.style.ERROR(f"Error calculating customer {customer_id}: {str(e)}"))
