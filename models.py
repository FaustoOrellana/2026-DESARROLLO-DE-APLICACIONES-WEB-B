from flask_login import UserMixin

class Usuario(UserMixin):

    def __init__(self, id, usuario, password=None):
        self.id = str(id)
        self.usuario = usuario
        self.password = password

    def __repr__(self):
        return f"<Usuario {self.usuario}>"