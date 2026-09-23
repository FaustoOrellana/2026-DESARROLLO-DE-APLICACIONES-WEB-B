from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, Optional

def coerce_int_or_none(valor):
    """Convierte de forma segura strings vacíos a None y números a int."""
    if valor is None or str(valor).strip() == '':
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None

class ProveedorForm(FlaskForm):
    nombre = StringField(
        'Empresa Proveedora / Razón Social',
        validators=[
            DataRequired(message='El nombre de la empresa es obligatorio.'),
            Length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres.')
        ]
    )
    contacto = StringField(
        'Persona de Contacto',
        validators=[
            DataRequired(message='El nombre de contacto es obligatorio.'),
            Length(min=3, max=80, message='El contacto debe tener entre 3 y 80 caracteres.')
        ]
    )
    telefono = StringField(
        'Teléfono',
        validators=[
            DataRequired(message='El teléfono es obligatorio.'),
            Length(min=7, max=20, message='El teléfono debe contener entre 7 y 20 caracteres.'),
            Regexp(r'^[0-9+\s\-]+$', message='Ingrese un número de teléfono válido.')
        ]
    )
    categoria = SelectField(
        'Categoría Principal',
        coerce=coerce_int_or_none,
        validators=[
            DataRequired(message='Debe seleccionar una categoría principal.')
        ]
    )
    id_ciudad = SelectField(
        'Ciudad',
        coerce=coerce_int_or_none,
        validators=[
            Optional()
        ]
    )
    submit = SubmitField('Guardar Proveedor')