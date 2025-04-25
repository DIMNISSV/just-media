# accounts/forms.py (Изменить)
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """
    A form that creates a user, with no privileges, from the given username and
    password. Uses the custom User model.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


class CustomUserChangeForm(UserChangeForm):
    """
    A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    password hash display field.
    """

    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
        'username', 'email', 'first_name', 'last_name', 'bio', 'is_active', 'is_staff', 'is_superuser', 'groups',
        'user_permissions')

class SignUpForm(CustomUserCreationForm):
    pass
