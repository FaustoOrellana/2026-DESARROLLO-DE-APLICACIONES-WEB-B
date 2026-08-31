from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length


class ProveedorForm(FlaskForm):
    nombre = StringField(
        'Empresa Proveedora',
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
            Length(min=9, max=20, message='El teléfono debe tener entre 9 y 20 caracteres.')
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