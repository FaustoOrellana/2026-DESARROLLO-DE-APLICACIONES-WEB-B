from flask_login import UserMixin

class Usuario(UserMixin):
    def __init__(self, id, usuario, password=None, rol='usuario', nombre=None, email=None):
        self.id = str(id)
        self.usuario = usuario
        self.password = password
        self.rol = str(rol).lower().strip() if rol else 'usuario'
        self.nombre = nombre or usuario
        self.email = email

    def __repr__(self):
        return f"<Usuario {self.usuario} ({self.rol})>"

    # --- MÉTODOS DE VALIDACIÓN DE ROL ---
    def es_admin(self):
        """Verifica si el usuario tiene privilegios de administrador."""
        return self.rol == 'admin'

    def tiene_rol(self, *roles):
        """
        Permite validar uno o varios roles simultáneamente.
        Uso: current_user.tiene_rol('admin', 'operador')
        """
        return self.rol in [r.lower() for r in roles]