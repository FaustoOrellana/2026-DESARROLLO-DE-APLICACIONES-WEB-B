from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class FacturacionForm(FlaskForm):
    numero = StringField(
        'Nº Factura',
        validators=[
            DataRequired(message='El número de factura es obligatorio.'),
            Length(min=3, max=30, message='El formato debe tener entre 3 y 30 caracteres.')
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
        places=2,
        validators=[
            DataRequired(message='El monto es obligatorio.'),
            NumberRange(min=0.01, max=1000000.0, message='El monto debe ser superior a 0.00.')
        ]
    )
    estado = SelectField(
        'Estado',
        coerce=str,
        choices=[
            ('', 'Seleccione un estado'),
            ('1', 'Pagada'),
            ('2', 'Pendiente'),
            ('3', 'Anulada')
        ],
        validators=[
            DataRequired(message='Debe seleccionar un estado válido.')
        ]
    )
    submit = SubmitField('Guardar Factura')