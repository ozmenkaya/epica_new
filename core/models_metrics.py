"""
Scoring and metrics models for suppliers and customers.
"""
from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


class CustomerFeedback(models.Model):
	"""Customer satisfaction survey after order delivery."""
	order = models.OneToOneField('billing.Order', on_delete=models.CASCADE, related_name='customer_feedback')
	supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='customer_feedbacks')
	customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='feedbacks_given')
	organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='customer_feedbacks')
	
	# 1-5 yıldız skorlar
	RATING_CHOICES = [(i, f"{i} Yıldız") for i in range(1, 6)]
	
	product_quality = models.IntegerField(choices=RATING_CHOICES, verbose_name="Ürün Kalitesi")
	communication = models.IntegerField(choices=RATING_CHOICES, verbose_name="İletişim Kalitesi")
	delivery_time = models.IntegerField(choices=RATING_CHOICES, verbose_name="Teslimat Süresi")
	overall_satisfaction = models.IntegerField(choices=RATING_CHOICES, verbose_name="Genel Memnuniyet")
	
	comment = models.TextField(blank=True, verbose_name="Yorumunuz")
	created_at = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ['-created_at']
		verbose_name = "Müşteri Geri Bildirimi"
		verbose_name_plural = "Müşteri Geri Bildirimleri"
		indexes = [
			models.Index(fields=['supplier', '-created_at']),
			models.Index(fields=['customer', '-created_at']),
			models.Index(fields=['organization', '-created_at']),
		]
	
	def __str__(self):
		return f"Feedback for Order #{self.order_id} by {self.customer.name}"
	
	@property
	def average_rating(self):
		"""4 kategorinin ortalaması (1-5 arası)"""
		return (self.product_quality + self.communication + 
				self.delivery_time + self.overall_satisfaction) / 4


class OwnerReview(models.Model):
	"""Owner/Admin manual review for suppliers or customers."""
	organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='owner_reviews')
	reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
	
	# Polimorfik: ya supplier ya da customer
	supplier = models.ForeignKey('Supplier', null=True, blank=True, on_delete=models.CASCADE, related_name='owner_reviews')
	customer = models.ForeignKey('Customer', null=True, blank=True, on_delete=models.CASCADE, related_name='owner_reviews')
	
	RATING_CHOICES = [(i, f"{i} Yıldız") for i in range(1, 6)]
	rating = models.IntegerField(choices=RATING_CHOICES, verbose_name="Puan")
	
	CATEGORY_CHOICES = [
		('reliability', 'Güvenilirlik'),
		('communication', 'İletişim'),
		('quality', 'Kalite'),
		('payment', 'Ödeme'),
		('pricing', 'Fiyatlama'),
		('other', 'Diğer'),
	]
	category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name="Kategori")
	comment = models.TextField(verbose_name="Yorum")
	created_at = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ['-created_at']
		verbose_name = "Owner Değerlendirmesi"
		verbose_name_plural = "Owner Değerlendirmeleri"
		indexes = [
			models.Index(fields=['supplier', '-created_at']),
			models.Index(fields=['customer', '-created_at']),
			models.Index(fields=['organization', '-created_at']),
		]
	
	def clean(self):
		from django.core.exceptions import ValidationError
		if not self.supplier and not self.customer:
			raise ValidationError("Supplier veya Customer seçilmeli.")
		if self.supplier and self.customer:
			raise ValidationError("Hem Supplier hem Customer seçilemez.")
	
	def __str__(self):
		target = self.supplier.name if self.supplier else self.customer.name
		return f"Review for {target} by {self.reviewer.username}"


class SupplierMetrics(models.Model):
	"""Calculated metrics and scores for suppliers (100 üzerinden skor)."""
	supplier = models.OneToOneField('Supplier', on_delete=models.CASCADE, related_name='metrics')
	organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='supplier_metrics')
	
	# Otomatik metrikler
	total_quotes_sent = models.IntegerField(default=0, verbose_name="Toplam Gönderilen Teklif")
	total_quotes_accepted = models.IntegerField(default=0, verbose_name="Kabul Edilen Teklif")
	win_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Kazanma Oranı %")
	
	avg_quote_response_hours = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Teklif Süresi (saat)")
	
	total_orders = models.IntegerField(default=0, verbose_name="Toplam Sipariş")
	completed_orders = models.IntegerField(default=0, verbose_name="Tamamlanan Sipariş")
	on_time_deliveries = models.IntegerField(default=0, verbose_name="Zamanında Teslimat")
	on_time_delivery_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Zamanında Teslimat %")
	
	# Manuel metrikler (anket ortalaması 1-5 arası)
	avg_product_quality = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Ürün Kalitesi")
	avg_communication = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. İletişim")
	avg_delivery_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Teslimat Puanı")
	avg_overall_satisfaction = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Genel Memnuniyet")
	total_feedback_count = models.IntegerField(default=0, verbose_name="Toplam Anket Sayısı")
	
	# Owner review ortalaması
	avg_owner_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Owner Değerlendirmesi")
	owner_review_count = models.IntegerField(default=0, verbose_name="Owner Değerlendirme Sayısı")
	
	# GENEL SKOR (0-100 arası)
	overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Genel Skor (100 üzerinden)")
	
	last_calculated = models.DateTimeField(auto_now=True, verbose_name="Son Hesaplama")
	
	class Meta:
		verbose_name = "Tedarikçi Metrikleri"
		verbose_name_plural = "Tedarikçi Metrikleri"
		ordering = ['-overall_score']
		indexes = [
			models.Index(fields=['organization', '-overall_score']),
			models.Index(fields=['-overall_score']),
		]
	
	def __str__(self):
		return f"{self.supplier.name} - Skor: {self.overall_score}/100"
	
	def calculate_score(self):
		"""
		100 üzerinden weighted score hesaplama:
		- Kazanma oranı: %20
		- Teklif hızı: %15 (hızlı = yüksek puan)
		- Zamanında teslimat: %20
		- Ürün kalitesi: %15
		- İletişim: %10
		- Genel memnuniyet: %15
		- Owner değerlendirmesi: %5
		"""
		score = Decimal('0.00')
		
		# Kazanma oranı (0-100)
		score += self.win_rate_percent * Decimal('0.20')
		
		# Teklif hızı (hızlı = yüksek puan, max 24 saat = 100 puan)
		if self.avg_quote_response_hours > 0:
			speed_score = max(0, 100 - (float(self.avg_quote_response_hours) / 24 * 100))
			score += Decimal(str(speed_score)) * Decimal('0.15')
		
		# Zamanında teslimat (0-100)
		score += self.on_time_delivery_percent * Decimal('0.20')
		
		# Anket skorları (1-5 -> 0-100)
		if self.total_feedback_count > 0:
			score += (self.avg_product_quality / Decimal('5.00')) * Decimal('100') * Decimal('0.15')
			score += (self.avg_communication / Decimal('5.00')) * Decimal('100') * Decimal('0.10')
			score += (self.avg_overall_satisfaction / Decimal('5.00')) * Decimal('100') * Decimal('0.15')
		
		# Owner review (1-5 -> 0-100)
		if self.owner_review_count > 0:
			score += (self.avg_owner_rating / Decimal('5.00')) * Decimal('100') * Decimal('0.05')
		
		self.overall_score = score
		return score


class CustomerMetrics(models.Model):
	"""Calculated metrics and scores for customers (100 üzerinden skor)."""
	customer = models.OneToOneField('Customer', on_delete=models.CASCADE, related_name='metrics')
	organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='customer_metrics')
	
	# Otomatik metrikler
	total_tickets_created = models.IntegerField(default=0, verbose_name="Toplam Talep")
	total_orders_placed = models.IntegerField(default=0, verbose_name="Verilen Sipariş")
	conversion_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Dönüşüm Oranı %")
	
	avg_response_time_hours = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Yanıt Süresi (saat)")
	
	cancelled_orders = models.IntegerField(default=0, verbose_name="İptal Edilen Sipariş")
	cancellation_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="İptal Oranı %")
	
	total_spent = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), verbose_name="Toplam Harcama")
	avg_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Sipariş Değeri")
	
	# Owner review ortalaması
	avg_owner_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'), verbose_name="Ort. Owner Değerlendirmesi")
	owner_review_count = models.IntegerField(default=0, verbose_name="Owner Değerlendirme Sayısı")
	
	# GENEL SKOR (0-100 arası)
	overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Genel Skor (100 üzerinden)")
	
	last_calculated = models.DateTimeField(auto_now=True, verbose_name="Son Hesaplama")
	
	class Meta:
		verbose_name = "Müşteri Metrikleri"
		verbose_name_plural = "Müşteri Metrikleri"
		ordering = ['-overall_score']
		indexes = [
			models.Index(fields=['organization', '-overall_score']),
			models.Index(fields=['-overall_score']),
		]
	
	def __str__(self):
		return f"{self.customer.name} - Skor: {self.overall_score}/100"
	
	def calculate_score(self):
		"""
		100 üzerinden weighted score hesaplama:
		- Dönüşüm oranı: %30
		- Düşük iptal oranı: %25
		- Yanıt hızı: %15
		- Harcama hacmi: %15
		- Owner değerlendirmesi: %15
		"""
		score = Decimal('0.00')
		
		# Dönüşüm oranı (0-100)
		score += self.conversion_rate_percent * Decimal('0.30')
		
		# Düşük iptal oranı (iptal yok = 100 puan)
		non_cancellation = Decimal('100.00') - self.cancellation_rate_percent
		score += non_cancellation * Decimal('0.25')
		
		# Yanıt hızı (hızlı = yüksek puan, max 48 saat = 100 puan)
		if self.avg_response_time_hours > 0:
			speed_score = max(0, 100 - (float(self.avg_response_time_hours) / 48 * 100))
			score += Decimal(str(speed_score)) * Decimal('0.15')
		
		# Harcama hacmi (logaritmik scale, 100K TL = 100 puan)
		if self.total_spent > 0:
			import math
			spending_score = min(100, (math.log10(float(self.total_spent) + 1) / 5) * 100)
			score += Decimal(str(spending_score)) * Decimal('0.15')
		
		# Owner review (1-5 -> 0-100)
		if self.owner_review_count > 0:
			score += (self.avg_owner_rating / Decimal('5.00')) * Decimal('100') * Decimal('0.15')
		
		self.overall_score = score
		return score
