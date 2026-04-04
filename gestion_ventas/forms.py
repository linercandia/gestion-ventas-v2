from django import forms
from django.forms import formset_factory

from .models import Adelanto, ControlZonaJornada, Jornada, Producto, Vendedor, Zona


class JornadaForm(forms.ModelForm):
    class Meta:
        model = Jornada
        fields = ["nombre", "fecha", "activa"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
        }


class InformeForm(forms.ModelForm):
    class Meta:
        model = ControlZonaJornada
        fields = ["nombre_vendedor", "dinero_entregado", "cerrada"]
        widgets = {
            "dinero_entregado": forms.TextInput(attrs={"class": "js-money", "inputmode": "numeric"}),
        }


class ZonaForm(forms.ModelForm):
    class Meta:
        model = Zona
        fields = ["nombre", "codigo", "descripcion", "activa"]


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["nombre", "codigo", "unidad_medida", "precio_venta", "activo"]
        widgets = {
            "precio_venta": forms.TextInput(attrs={"class": "js-money", "inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidad_medida"].help_text = "Si eliges Unidad, se registra en unidades. Si eliges Libra, se registra en pesos."


class VendedorForm(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = ["nombre", "telefono", "identificacion", "zona_preferida", "activo"]

    def __init__(self, *args, **kwargs):
        zonas = kwargs.pop("zonas", None)
        super().__init__(*args, **kwargs)
        if zonas is not None:
            self.fields["zona_preferida"].queryset = zonas


class AdelantoForm(forms.ModelForm):
    class Meta:
        model = Adelanto
        fields = ["vendedor", "control", "fecha", "monto", "motivo"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "monto": forms.TextInput(attrs={"class": "js-money", "inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        vendedores = kwargs.pop("vendedores", None)
        controles = kwargs.pop("controles", None)
        super().__init__(*args, **kwargs)
        if vendedores is not None:
            self.fields["vendedor"].queryset = vendedores
        if controles is not None:
            self.fields["control"].queryset = controles
            self.fields["control"].required = False


class DesprendiblePagoForm(forms.Form):
    vendedor = forms.ModelChoiceField(queryset=Vendedor.objects.none(), required=False)
    fecha_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=False)
    fecha_fin = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=False)

    def __init__(self, *args, **kwargs):
        vendedores = kwargs.pop("vendedores", None)
        super().__init__(*args, **kwargs)
        if vendedores is not None:
            self.fields["vendedor"].queryset = vendedores


class InformeFiltroForm(forms.Form):
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=False)
    vendedor = forms.ModelChoiceField(queryset=Vendedor.objects.none(), required=False)
    zona = forms.ModelChoiceField(queryset=Zona.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        vendedores = kwargs.pop("vendedores", None)
        zonas = kwargs.pop("zonas", None)
        super().__init__(*args, **kwargs)
        if vendedores is not None:
            self.fields["vendedor"].queryset = vendedores
        if zonas is not None:
            self.fields["zona"].queryset = zonas


class ZonaProductoComisionForm(forms.Form):
    producto_id = forms.IntegerField(widget=forms.HiddenInput)
    producto_nombre = forms.CharField(disabled=True, required=False)
    porcentaje_comision = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )


ZonaProductoComisionFormSet = formset_factory(ZonaProductoComisionForm, extra=0)
