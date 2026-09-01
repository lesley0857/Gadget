# solar/forms.py

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Appliance,
    SolarDesign,
    DesignSetting,
)


# ================================================================
# COMMON STYLING
# ================================================================

TEXT_INPUT_CLASS = "form-control"
SELECT_INPUT_CLASS = "form-select"
NUMBER_INPUT_CLASS = "form-control"


# ================================================================
# SOLAR DESIGN FORM
# ================================================================

class SolarDesignForm(forms.ModelForm):

    class Meta:
        model = SolarDesign

        fields = (
            "project_name",
            "client_name",
            "project_location",
            "description",
            "installation_type",
            "operating_mode",
            "peak_sun_hours",
        )

        widgets = {
            "project_name": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASS,
                    "placeholder": "Project name",
                }
            ),

            "client_name": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASS,
                    "placeholder": "Client name",
                }
            ),

            "project_location": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASS,
                    "placeholder": "Project location",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": TEXT_INPUT_CLASS,
                    "rows": 3,
                    "placeholder": "Project description",
                }
            ),

            "operating_mode": forms.Select(
                attrs={
                    "class": SELECT_INPUT_CLASS,
                }
            ),

            "installation_type": forms.Select(
                attrs={"class": SELECT_INPUT_CLASS}
            ),

            "peak_sun_hours": forms.NumberInput(
                attrs={
                    "class": NUMBER_INPUT_CLASS,
                    "step": "0.01",
                    "min": "0.1",
                    "max": "24",
                }
            ),
        }

        labels = {
            "project_name": "Project Name",
            "client_name": "Client Name",
            "project_location": "Project Location",
            "description": "Project Description",
            "operating_mode": "System Type",
            "installation_type": "Project Type",
            "peak_sun_hours": "Peak Sun Hours",
        }

        help_texts = {
            "peak_sun_hours": (
                "Average daily peak sun hours for the project location."
            ),
        }

    def clean_project_name(self):
        value = self.cleaned_data.get("project_name")

        if not value or not value.strip():
            raise ValidationError(
                "Project name is required."
            )

        return value.strip()

    def clean_peak_sun_hours(self):
        value = self.cleaned_data.get("peak_sun_hours")

        if value is None:
            raise ValidationError(
                "Peak Sun Hours is required."
            )

        if value <= Decimal("0"):
            raise ValidationError(
                "Peak Sun Hours must be greater than zero."
            )

        if value > Decimal("24"):
            raise ValidationError(
                "Peak Sun Hours cannot exceed 24 hours."
            )

        return value


# ================================================================
# APPLIANCE SELECT
# ================================================================

class ApplianceSelect(forms.Select):
    """
    Select widget that exposes appliance engineering data
    through HTML data-* attributes.

    The JavaScript uses these attributes for UI feedback only.
    """

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):

        option = super().create_option(
            name=name,
            value=value,
            label=label,
            selected=selected,
            index=index,
            subindex=subindex,
            attrs=attrs,
        )

        appliance = getattr(value, "instance", None)

        if appliance is not None:

            option["attrs"].update({
                "data-wattage": str(appliance.wattage),
                "data-surge-factor": str(appliance.surge_factor),
                "data-load-type": appliance.load_type or "",
                "data-starting-type": appliance.starting_type or "",
                "data-category": appliance.category or "",
                "data-installation-type": appliance.installation_type or "residential",
            })

        return option


# ================================================================
# LOAD ITEM FORM
# ================================================================

class LoadItemForm(forms.Form):

    appliance = forms.ModelChoiceField(
        queryset=Appliance.objects.filter(
            wattage__gt=0
        ).order_by(
            "category",
            "name",
        ),
        required=False,
        empty_label="Select appliance",
        widget=ApplianceSelect(
            attrs={
                "class": SELECT_INPUT_CLASS,
                "data-appliance-select": "true",
            }
        ),
        label="Appliance",
    )

    custom_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS, "placeholder": "Custom appliance name"}),
        label="Custom appliance",
    )

    custom_wattage = forms.DecimalField(
        required=False,
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": NUMBER_INPUT_CLASS, "placeholder": "Watts", "min": "0.01", "step": "0.01"}),
        label="Custom wattage",
    )

    quantity = forms.IntegerField(
        required=True,
        min_value=1,
        max_value=10000,
        initial=1,
        widget=forms.NumberInput(
            attrs={
                "class": NUMBER_INPUT_CLASS,
                "min": "1",
                "step": "1",
            }
        ),
        label="Quantity",
    )

    hours_per_day = forms.DecimalField(
        required=True,
        min_value=Decimal("0.01"),
        max_value=Decimal("24"),
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": NUMBER_INPUT_CLASS,
                "min": "0.01",
                "max": "24",
                "step": "0.01",
            }
        ),
        label="Hours / Day",
    )

    def clean(self):

        cleaned_data = super().clean()

        appliance = cleaned_data.get("appliance")
        custom_name = (cleaned_data.get("custom_name") or "").strip()
        custom_wattage = cleaned_data.get("custom_wattage")
        quantity = cleaned_data.get("quantity")
        hours = cleaned_data.get("hours_per_day")

        # Allow the formset to determine whether a completely
        # empty extra form should be ignored.
        # The quantity widget defaults to 1, so it must not turn an otherwise
        # blank extra formset row into a validation error.
        if not appliance and not custom_name and custom_wattage is None and hours in (None, ""):
            return cleaned_data

        if appliance is None and not custom_name:
            self.add_error(
                "appliance",
                "Select an appliance or enter a custom appliance.",
            )
            return cleaned_data

        if appliance is None and custom_wattage is None:
            self.add_error("custom_wattage", "Custom appliance wattage is required.")

        if quantity is None:
            self.add_error(
                "quantity",
                "Quantity is required.",
            )

        elif quantity < 1:
            self.add_error(
                "quantity",
                "Quantity must be at least 1.",
            )

        if hours is None:
            self.add_error(
                "hours_per_day",
                "Hours per day is required.",
            )

        elif hours <= Decimal("0"):
            self.add_error(
                "hours_per_day",
                "Hours per day must be greater than zero.",
            )

        elif hours > Decimal("24"):
            self.add_error(
                "hours_per_day",
                "Hours per day cannot exceed 24.",
            )

        return cleaned_data


# ================================================================
# COMPATIBILITY ALIAS
# ================================================================

ApplianceLoadForm = LoadItemForm


# ================================================================
# LOAD FORMSET
# ================================================================

LoadItemFormSet = forms.formset_factory(
    LoadItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ================================================================
# BATTERY PREFERENCE FORM
# ================================================================

class BatteryPreferenceForm(forms.Form):

    battery_type = forms.ChoiceField(
        required=False,
        choices=(
            ("", "Automatic"),
            ("lead_acid", "Lead Acid"),
            ("lithium", "Lithium"),
        ),
        widget=forms.Select(
            attrs={
                "class": SELECT_INPUT_CLASS,
            }
        ),
        label="Battery Chemistry Preference",
    )

    require_hybrid_battery = forms.BooleanField(
        required=False,
        label="Hybrid-compatible battery only",
        help_text="Show batteries configured for hybrid inverter systems.",
    )

    solution_preference = forms.ChoiceField(
        required=False,
        choices=(
            ("components", "Component system (recommended)"),
            ("generator", "Offer a compatible all-in-one solar generator"),
        ),
        initial="components",
        widget=forms.Select(attrs={"class": SELECT_INPUT_CLASS}),
        label="Preferred solution",
        help_text="Generators are offered as a catalogue alternative when their output and stored energy meet the load.",
    )

    def clean_battery_type(self):

        value = self.cleaned_data.get("battery_type")

        if not value:
            return None

        return value


# ================================================================
# DESIGN REQUIREMENTS
# ================================================================

class DesignRequirementsForm(forms.Form):

    autonomy_days = forms.DecimalField(
        required=True,
        min_value=Decimal("0"),
        max_value=Decimal("30"),
        max_digits=6,
        decimal_places=2,
        initial=Decimal("1"),
        widget=forms.NumberInput(
            attrs={
                "class": NUMBER_INPUT_CLASS,
                "min": "0",
                "max": "30",
                "step": "0.1",
            }
        ),
        label="Battery Autonomy",
        help_text=(
            "Required battery autonomy in days. "
            "For grid-tied systems this may be zero."
        ),
    )

    future_expansion = forms.DecimalField(
        required=True,
        min_value=Decimal("1"),
        max_value=Decimal("3"),
        max_digits=6,
        decimal_places=3,
        initial=Decimal("1.20"),
        widget=forms.NumberInput(
            attrs={
                "class": NUMBER_INPUT_CLASS,
                "min": "1",
                "max": "3",
                "step": "0.01",
            }
        ),
        label="Future Expansion Factor",
    )

    def clean_autonomy_days(self):

        value = self.cleaned_data.get("autonomy_days")

        if value is None:
            return Decimal("1")

        if value < Decimal("0"):
            raise ValidationError(
                "Autonomy cannot be negative."
            )

        return value

    def clean_future_expansion(self):

        value = self.cleaned_data.get("future_expansion")

        if value is None:
            return Decimal("1.20")

        if value < Decimal("1"):
            raise ValidationError(
                "Future expansion factor must be at least 1.0."
            )

        return value
