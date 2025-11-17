from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class CaseInsensitiveModelBackend(ModelBackend):
    """
    Case-insensitive authentication backend.
    Allows users to login with any case variation of their username.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        try:
            # Try case-insensitive lookup
            user = UserModel.objects.get(
                Q(**{f'{UserModel.USERNAME_FIELD}__iexact': username})
            )
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user (#20760).
            UserModel().set_password(password)
        except UserModel.MultipleObjectsReturned:
            # Multiple users with same username (different cases) - use exact match
            return super().authenticate(request, username=username, password=password, **kwargs)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
