from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp


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
        choices=[
            ('', 'Seleccione una categoría'),
            ('Hardware', 'Hardware'),
            ('Redes', 'Redes'),
            ('Licencias', 'Licencias'),
            ('Software', 'Software'),
            ('Almacenamiento', 'Almacenamiento')
        ],
        validators=[
            DataRequired(message='Debe seleccionar una categoría válida.')
        ]
    )
    precio = DecimalField(
        'Precio ($)',
        validators=[
            DataRequired(message='El precio es obligatorio.'),
            NumberRange(min=0.01, max=100000.0, message='El precio debe ser mayor a 0 y menor a $100,000.')
        ]
    )
    stock = IntegerField(
        'Stock',
        validators=[
            DataRequired(message='El stock es obligatorio.'),
            NumberRange(min=0, max=10000, message='El stock debe estar entre 0 y 10,000 unidades.')
        ]
    )
    submit = SubmitField('Guardar')