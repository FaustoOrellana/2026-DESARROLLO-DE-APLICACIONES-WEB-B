from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

def coerce_int_or_none(valor):
    """Convierte de forma segura strings vacíos a None y números a int."""
    if valor is None or str(valor).strip() == '':
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
            DataRequired(message='Debe seleccionar un cliente activo.')
        ]
    )
    fecha = DateField(
        'Fecha de Emisión',
        format='%Y-%m-%d',
        validators=[
            DataRequired(message='La fecha de emisión es obligatoria.')
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
    # Regla estricta: solo se permite emitir en estado PAGADA
    estado = SelectField(
        'Estado de Cobro',
        coerce=coerce_int_or_none,
        choices=[
            (1, 'Pagada (Cobro confirmado)')
        ],
        default=1,
        validators=[
            DataRequired(message='La factura solo se puede emitir con cobro confirmado (Pagada).')
        ]
    )
    submit = SubmitField('Emitir y Procesar Factura')