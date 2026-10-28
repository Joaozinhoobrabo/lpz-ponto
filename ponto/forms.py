from django import forms

from .models import Employee, PunchEvent


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "user", "full_name", "enrollment", "email", "position", "department",
            "hire_date", "schedule", "is_active",
        ]
        widgets = {"hire_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = self.fields["user"].queryset.filter(employee__isnull=True)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field-input"


class PunchForm(forms.Form):
    kind = forms.ChoiceField(choices=PunchEvent.Kind.choices, widget=forms.HiddenInput)
    latitude = forms.DecimalField(required=False, min_value=-90, max_value=90, widget=forms.HiddenInput)
    longitude = forms.DecimalField(required=False, min_value=-180, max_value=180, widget=forms.HiddenInput)
    accuracy_meters = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)
    location_status = forms.ChoiceField(
        required=False, choices=PunchEvent.LocationStatus.choices, widget=forms.HiddenInput
    )
    location_reason = forms.CharField(required=False, max_length=160, widget=forms.HiddenInput)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("location_status") == PunchEvent.LocationStatus.CAPTURED:
            if cleaned_data.get("latitude") is None or cleaned_data.get("longitude") is None:
                raise forms.ValidationError("A localização retornou dados incompletos.")
        elif cleaned_data.get("latitude") is not None or cleaned_data.get("longitude") is not None:
            raise forms.ValidationError("Coordenadas recebidas sem estado de localização válido.")
        return cleaned_data