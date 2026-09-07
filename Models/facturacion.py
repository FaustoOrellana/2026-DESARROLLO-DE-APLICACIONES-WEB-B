from extensiones import db

class Factura(db.Model):
    __tablename__ = 'facturas'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    numero = db.Column(db.String, nullable=False, unique=True)
    cliente = db.Column(db.String, nullable=False)
    fecha = db.Column(db.String, nullable=False)
    monto = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String, nullable=False)