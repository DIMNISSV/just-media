# accounts/urls.py
from django.urls import path
from . import views

app_name = 'accounts'  # Define app namespace

urlpatterns = [
    path('signup/', views.SignUpView.as_view(), name='signup'),
    # Add other account-related URLs here later (e.g., profile view)
]
