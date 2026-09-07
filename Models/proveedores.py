from extensiones import db

class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String, nullable=False)
    contacto = db.Column(db.String, nullable=False)
    telefono = db.Column(db.String, nullable=False)
    categoria = db.Column(db.String, nullable=False)