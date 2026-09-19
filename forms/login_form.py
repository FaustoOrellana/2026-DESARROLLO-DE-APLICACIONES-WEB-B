from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    usuario = StringField('Nombre de Usuario', validators=[
        DataRequired(message='El nombre de usuario es obligatorio.')
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message='La contraseña es obligatoria.')
    ])
    submit = SubmitField('Iniciar Sesión')