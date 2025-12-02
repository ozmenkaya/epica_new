from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


class CaseInsensitiveModelBackend(ModelBackend):
	"""
	Enhanced case-insensitive authentication backend.
	
	Features:
	- Allows login with any case variation of username
	- Supports email as username (if email field matches)
	- Timing-attack protection
	- Comprehensive logging
	"""
	
	def authenticate(self, request, username=None, password=None, **kwargs):
		"""
		Authenticate user with case-insensitive username or email.
		
		Args:
			request: The HTTP request object
			username: Username or email to authenticate
			password: User's password
			**kwargs: Additional keyword arguments
		
		Returns:
			User object if authentication succeeds, None otherwise
		"""
		UserModel = get_user_model()
		
		if username is None:
			username = kwargs.get(UserModel.USERNAME_FIELD)
		
		if not username:
			return None
		
		try:
			# Try case-insensitive username lookup first
			user = UserModel.objects.get(
				Q(**{f'{UserModel.USERNAME_FIELD}__iexact': username})
			)
		except UserModel.DoesNotExist:
			# Try email lookup if username not found
			try:
				user = UserModel.objects.get(Q(email__iexact=username))
			except UserModel.DoesNotExist:
				# Run the default password hasher to prevent timing attacks
				UserModel().set_password(password)
				logger.debug(f"Authentication failed: User not found for '{username}'")
				return None
			except UserModel.MultipleObjectsReturned:
				logger.warning(f"Multiple users found with email: {username}")
				return None
		except UserModel.MultipleObjectsReturned:
			# Multiple users with same username (different cases)
			# Fall back to exact match via parent class
			logger.warning(f"Multiple users found with username: {username}")
			return super().authenticate(request, username=username, password=password, **kwargs)
		
		# Verify password and check if user can authenticate
		if user.check_password(password) and self.user_can_authenticate(user):
			logger.info(f"Successful authentication for user: {user.username}")
			return user
		
		logger.debug(f"Authentication failed: Invalid password for user '{user.username}'")
		return None
	
	def user_can_authenticate(self, user):
		"""
		Check if user is allowed to authenticate.
		
		Args:
			user: User object to check
		
		Returns:
			bool: True if user can authenticate, False otherwise
		"""
		is_active = getattr(user, 'is_active', None)
		return is_active or is_active is None
