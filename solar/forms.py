# solar/forms.py

from django import forms

from .models import (
    Battery,
    SolarPanel,
    Appliance,
    DesignSetting
)


class SolarCalculatorForm(forms.Form):

    ##################################
    # SYSTEM SETTINGS
    ##################################

    # autonomy = forms.IntegerField(
    #     initial=1,
    #     min_value=1,
    #     label="Battery Autonomy (Days)"
    # )

    peak_sun_hours = forms.FloatField(
        initial=5,
        label="Peak Sun Hours"
    )

    ##################################
    # BATTERY
    ##################################

    battery = forms.ModelChoiceField(
        queryset=Battery.objects.filter(
            active=True
        ),
        empty_label="Select Battery"
    )

    ##################################
    # SOLAR PANEL
    ##################################

    panel = forms.ModelChoiceField(
        queryset=SolarPanel.objects.filter(
            active=True
        ),
        empty_label="Select Solar Panel"
    )

    ##################################
    # INSTALLATION DISTANCES
    ##################################

    pv_distance = forms.FloatField(
        initial=20,
        label="PV Cable Distance (m)"
    )

    battery_distance = forms.FloatField(
        initial=3,
        label="Battery Cable Distance (m)"
    )

    ac_distance = forms.FloatField(
        initial=15,
        label="AC Cable Distance (m)"
    )

    operating_mode = forms.ChoiceField(
        choices=[
            ("off_grid", "Off-grid"),
            ("solar_battery", "Solar + battery"),
            ("backup", "Backup"),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select"
            }
        ),
        initial="solar_battery",
        label="System Operating Mode"
    )