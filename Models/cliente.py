from extensiones import db

class Cliente(db.Model):
    __tablename__ = 'clientes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String, nullable=False)
    ruc = db.Column(db.String, nullable=False, unique=True)
    telefono = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)