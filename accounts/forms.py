# accounts/forms.py
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    """
    A form that creates a user, with no privileges, from the given username and
    password. Extends the default UserCreationForm if needed later.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
