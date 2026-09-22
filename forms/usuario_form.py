from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp

class UsuarioForm(FlaskForm):
    usuario = StringField('Nombre de Usuario', validators=[
        DataRequired(message="El usuario es obligatorio."),
        Length(min=3, max=50, message="El usuario debe tener entre 3 y 50 caracteres.")
    ])
    
    ruc = StringField('Cédula o RUC', validators=[
        DataRequired(message="La identificación es obligatoria para la facturación."),
        Length(min=10, max=13, message="Debe tener 10 dígitos (cédula) o 13 (RUC)."),
        Regexp(r'^[0-9]+$', message="Solo se permiten números.")
    ])

    email = StringField('Correo Electrónico', validators=[
        DataRequired(message="El correo es obligatorio."),
        Email(message="Ingrese un correo válido.")
    ])
    
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria."),
        Length(min=6, message="Mínimo 6 caracteres.")
    ])
    
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message="Confirme su contraseña."),
        EqualTo('password', message="Las contraseñas no coinciden.")
    ])
    
    captcha = StringField('Código de Seguridad', validators=[
        DataRequired(message="Ingrese el código de seguridad.")
    ])
    
    submit = SubmitField('Registrarse')