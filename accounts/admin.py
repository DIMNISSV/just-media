# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import SignUpForm
from .models import User


# Определяем кастомную админку, если нужно добавить поля
class UserAdmin(BaseUserAdmin):
    # Используем нашу форму для создания пользователя в админке
    add_form = SignUpForm

    # Поля, отображаемые в списке пользователей
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')

    # Поля, отображаемые при редактировании пользователя
    # Добавляем 'bio' в стандартные fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        (_('Profile Info'), {'fields': ('bio',)}),
    )
    # Поля, отображаемые при создании пользователя
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_('Profile Info'), {'fields': ('bio', 'first_name', 'last_name', 'email')}),
    )
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)


# Регистрируем нашу модель User с кастомной админкой
admin.site.register(User, UserAdmin)
