from django import forms


class AccessCodeForm(forms.Form):
    code = forms.CharField(
        label="Código de acesso",
        strip=False,
        max_length=256,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "autofocus": True,
            "class": "field-input",
        }),
    )
