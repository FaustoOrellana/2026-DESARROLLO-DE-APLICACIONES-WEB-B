from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp


class FacturacionForm(FlaskForm):
    numero = StringField(
        'Nº Factura',
        validators=[
            DataRequired(message='El número de factura es obligatorio.'),
            Length(min=7, max=25, message='El formato debe tener entre 7 y 25 caracteres.')
        ]
    )
    cliente = SelectField(
        'Cliente',
        coerce=str,
        validators=[
            DataRequired(message='Debe seleccionar un cliente de la lista.')
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
        validators=[
            DataRequired(message='El monto es obligatorio.'),
            NumberRange(min=0.01, max=500000.0, message='El monto debe ser superior a 0.00.')
        ]
    )
    estado = SelectField(
        'Estado',
        choices=[
            ('', 'Seleccione un estado'),
            ('Pagada', 'Pagada'),
            ('Pendiente', 'Pendiente'),
            ('Anulada', 'Anulada')
        ],
        validators=[
            DataRequired(message='Debe seleccionar un estado válido.')
        ]
    )
    submit = SubmitField('Guardar')