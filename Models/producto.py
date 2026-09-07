from extensiones import db

class Producto(db.Model):
    __tablename__ = 'productos'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String, nullable=False)
    categoria = db.Column(db.String)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)