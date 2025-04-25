# accounts/views.py
from django.urls import reverse_lazy
from django.views import generic

from .forms import SignUpForm


class SignUpView(generic.CreateView):
    """
    View for user registration using the SignUpForm.
    """
    form_class = SignUpForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'
