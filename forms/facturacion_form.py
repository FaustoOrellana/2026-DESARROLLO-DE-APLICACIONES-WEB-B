from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Length, Optional, NumberRange


def coerce_int_or_none(valor):
    """Convierte de forma segura strings vacíos o nulos a None y números a int."""
    if valor is None or str(valor).strip() in ('', 'None', 'null'):
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None


class FacturacionForm(FlaskForm):
    numero = StringField(
        'Nº Factura',
        validators=[
            DataRequired(message='El número de factura es obligatorio.'),
            Length(min=3, max=30, message='El formato debe tener entre 3 y 30 caracteres.')
        ]
    )
    cliente = SelectField(
        'Cliente / Razón Social',
        coerce=coerce_int_or_none,
        validators=[
            InputRequired(message='Debe seleccionar un cliente activo.')
        ]
    )
    fecha = DateField(
        'Fecha de Emisión',
        format='%Y-%m-%d',
        validators=[
            InputRequired(message='La fecha de emisión es obligatoria.')
        ]
    )
    monto = DecimalField(
        'Monto Total ($)',
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0.0, max=1000000.0, message='El monto debe ser un valor positivo.')
        ]
    )
    # Permite validación compatible tanto para emisión (Pagada) como para auditoría/edición
    estado = SelectField(
        'Estado de Cobro',
        coerce=coerce_int_or_none,
        choices=[
            (1, 'Pagada (Cobro confirmado)'),
            (2, 'Pendiente de Pago'),
            (3, 'Anulada')
        ],
        default=1,
        validators=[
            InputRequired(message='Debe definir el estado de cobro de la factura.')
        ]
    )
    submit = SubmitField('Emitir y Procesar Factura')