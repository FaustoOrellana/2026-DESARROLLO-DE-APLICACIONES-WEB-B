from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp


class ProveedorForm(FlaskForm):

    nombre = StringField(
        'Empresa Proveedora',
        validators=[
            DataRequired(message='El nombre de la empresa es obligatorio.'),
            Length(min=3, max=100, message='Debe contener entre 3 y 100 caracteres.')
        ]
    )

    contacto = StringField(
        'Persona de Contacto',
        validators=[
            DataRequired(message='El nombre del contacto es obligatorio.'),
            Length(min=3, max=80, message='Debe contener entre 3 y 80 caracteres.')
        ]
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            DataRequired(message='El teléfono es obligatorio.'),
            Length(min=9, max=15, message='El teléfono debe contener entre 9 y 15 dígitos.'),
            Regexp(r'^[0-9+ ]+$', message='Ingrese un formato de teléfono válido.')
        ]
    )

    categoria = SelectField(
        'Categoría Principal',
        choices=[
            ('', 'Seleccione una categoría'),
            ('Hardware y Equipos', 'Hardware y Equipos'),
            ('Software y Licencias', 'Software y Licencias'),
            ('Infraestructura de Red', 'Infraestructura de Red'),
            ('Servicios y Soporte', 'Servicios y Soporte')
        ],
        validators=[
            DataRequired(message='Debe seleccionar una categoría principal.')
        ]
    )

    submit = SubmitField('Guardar')