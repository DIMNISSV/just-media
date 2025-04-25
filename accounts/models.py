# accounts/models.py (Изменить)
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom user model inheriting from AbstractUser.
    Uses username as the primary identifier.
    Includes a unique email field and a bio field.
    """
    email = models.EmailField(
        _('email address'),
        unique=True,
        error_messages={
            'unique': _("A user with that email already exists."),
        }
    )

    bio = models.TextField(_("Biography"), blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.username
