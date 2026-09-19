from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo

class UsuarioForm(FlaskForm):
    usuario = StringField('Nombre de Usuario', validators=[
        DataRequired(message='El nombre de usuario es obligatorio.'),
        Length(min=4, max=50, message='El usuario debe tener entre 4 y 50 caracteres.')
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.'),
        Length(min=6, max=100, message='La contraseña debe tener al menos 6 caracteres.')
    ])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message='Debe confirmar la contraseña.'),
        EqualTo('password', message='Las contraseñas no coinciden.')
    ])
    submit = SubmitField('Registrar Usuario')