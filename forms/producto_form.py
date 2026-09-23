from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

def coerce_int_or_none(valor):
    """Convierte de forma segura strings vacíos a None y números a int."""
    if valor is None or str(valor).strip() == '':
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None

class ProductoForm(FlaskForm):
    nombre = StringField(
        'Nombre del Producto',
        validators=[
            DataRequired(message='El nombre del producto es obligatorio.'),
            Length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres.')
        ]
    )
    categoria = SelectField(
        'Categoría',
        coerce=coerce_int_or_none,
        validators=[
            DataRequired(message='Debe seleccionar una categoría válida.')
        ]
    )
    marca = SelectField(
        'Marca',
        coerce=coerce_int_or_none,
        validators=[
            Optional()
        ]
    )
    precio = DecimalField(
        'Precio ($)',
        places=2,
        validators=[
            DataRequired(message='El precio es obligatorio.'),
            NumberRange(min=0.01, max=100000.0, message='El precio debe ser mayor a 0 y menor a $100,000.')
        ]
    )
    stock = IntegerField(
        'Stock',
        validators=[
            InputRequired(message='El stock es obligatorio.'),
            NumberRange(min=0, max=10000, message='El stock debe estar entre 0 y 10,000 unidades.')
        ]
    )
    descripcion = TextAreaField(
        'Descripción',
        validators=[
            Optional(),
            Length(max=500, message='La descripción no puede exceder los 500 caracteres.')
        ]
    )
    submit = SubmitField('Guardar Producto')