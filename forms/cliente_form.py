from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp


class ClienteForm(FlaskForm):

    nombre = StringField(
        'Nombre / Razón Social',
        validators=[
            DataRequired(message='El nombre del cliente es obligatorio.'),
            Length(min=3, max=100, message='El nombre debe tener entre 3 y 100 caracteres.')
        ]
    )

    ruc = StringField(
        'RUC / Cédula',
        validators=[
            DataRequired(message='La identificación es obligatoria.'),
            Length(min=10, max=13, message='Debe contener entre 10 y 13 dígitos.'),
            Regexp(r'^[0-9]+$', message='La identificación solo debe contener números.')
        ]
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            DataRequired(message='El teléfono es obligatorio.'),
            Length(min=9, max=20, message='El teléfono debe contener entre 9 y 20 caracteres.')
        ]
    )

    email = StringField(
        'Correo Electrónico',
        validators=[
            DataRequired(message='El correo electrónico es obligatorio.'),
            Regexp(
                r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
                message='Ingrese un correo válido (ej: usuario@dominio.com).'
            )
        ]
    )

    submit = SubmitField('Guardar')