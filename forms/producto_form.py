from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Regexp


class ProductoForm(FlaskForm):

    nombre = StringField(
        'Nombre del Producto',
        validators=[
            DataRequired(message='El nombre del producto es obligatorio.'),
            Length(min=3, max=100, message='Debe tener entre 3 y 100 caracteres.')
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
            NumberRange(min=0.01, message='El precio debe ser un valor mayor a 0.')
        ]
    )

    stock = IntegerField(
        'Stock',
        validators=[
            DataRequired(message='El stock es obligatorio.'),
            NumberRange(min=0, message='El stock no puede ser un número negativo.')
        ]
    )

    submit = SubmitField('Guardar')