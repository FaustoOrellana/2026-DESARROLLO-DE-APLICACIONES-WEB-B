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
    captcha = StringField('Código de Seguridad', validators=[
        DataRequired(message='El código CAPTCHA es obligatorio.')
    ])
    submit = SubmitField('Iniciar Sesión')