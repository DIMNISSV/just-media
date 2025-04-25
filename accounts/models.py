# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom user model inheriting from AbstractUser.
    Uses username as the primary identifier.
    Includes email and a bio field.
    """
    email = models.EmailField(_('email address'), blank=True)

    bio = models.TextField(_("Biography"), blank=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        # ordering = ['username'] # Можно добавить, если нужно

    def __str__(self):
        return self.username
