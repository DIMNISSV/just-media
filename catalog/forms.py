# catalog/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Genre, MediaItem


class AdvancedMediaSearchForm(forms.Form):
    """Form for advanced filtering of MediaItems."""
    q = forms.CharField(
        label=_("Title contains"),
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': _('Search title...')})
    )
    year_from = forms.IntegerField(
        label=_("Year from"),
        required=False,
        min_value=1900,  # Or query min year from DB?
        max_value=2100,  # Or query max year?
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': _('e.g., 1995')})
    )
    year_to = forms.IntegerField(
        label=_("Year to"),
        required=False,
        min_value=1900,
        max_value=2100,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': _('e.g., 2023')})
    )
    # Use generic types for filtering
    media_type = forms.ChoiceField(
        label=_("Media Type"),
        required=False,
        choices=[('', _('Any Type'))] + MediaItem.MediaType.choices,  # Add 'Any' option
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    genres = forms.ModelMultipleChoiceField(
        label=_("Genres"),
        required=False,
        queryset=Genre.objects.all().order_by('name'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select form-select-sm', 'size': '5'})
        # Allow multiple selections
    )

    # Optional: Add sorting field?
    # sort_by = forms.ChoiceField(...)

    def clean(self):
        """Validate year range."""
        cleaned_data = super().clean()
        year_from = cleaned_data.get('year_from')
        year_to = cleaned_data.get('year_to')
        if year_from and year_to and year_from > year_to:
            raise forms.ValidationError(_("'Year from' cannot be greater than 'Year to'."))
        return cleaned_data
