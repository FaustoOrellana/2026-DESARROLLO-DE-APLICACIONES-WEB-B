from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp


class FacturacionForm(FlaskForm):

    numero = StringField(
        'Nº Factura',
        validators=[
            DataRequired(message='El número de comprobante es obligatorio.'),
            Length(min=5, max=20, message='El número de factura debe contener entre 5 y 20 caracteres.'),
            Regexp(r'^[A-Za-z0-9\-]+$', message='Solo se permiten letras, números y guiones (ej. FAC-001-00240).')
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
            NumberRange(min=0.01, message='El monto debe ser superior a 0.00.')
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
            DataRequired(message='Debe asignar un estado a la factura.')
        ]
    )

    submit = SubmitField('Guardar')