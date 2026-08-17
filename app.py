from flask import Flask, render_template

app = Flask(__name__)

# Datos de ejemplo para renderizar en los módulos
PRODUCTOS = [
    {"id": 1, "nombre": "Servidor Dell PowerEdge R740", "categoria": "Hardware", "precio": 3500.00, "stock": 5},
    {"id": 2, "nombre": "Switch Cisco Catalyst 2960", "categoria": "Redes", "precio": 1200.00, "stock": 12},
    {"id": 3, "nombre": "Licencia Windows Server 2022 Datacenter", "categoria": "Licencias", "precio": 850.00, "stock": 30},
    {"id": 4, "nombre": "Licencia Antivirus Kaspersky Endpoint", "categoria": "Software", "precio": 45.00, "stock": 100}
]

CLIENTES = [
    {"id": 1, "nombre": "Corporación El Sol S.A.", "ruc": "0992345678001", "telefono": "+593 98 123 4567", "email": "contacto@elsol.com"},
    {"id": 2, "nombre": "Universidad Estatal Amazónica", "ruc": "1660001230001", "telefono": "+593 98 885 8100", "email": "info@uea.edu.ec"},
    {"id": 3, "nombre": "Proviseguridad Cía. Ltda.", "ruc": "0791234567001", "telefono": "+593 93 999 8888", "email": "operaciones@proviseguridad.com"}
]

PROVEEDORES = [
    {"id": 1, "empresa": "TechSupply Ecuador", "contacto": "Carlos Mendoza", "telefono": "+593 99 876 5432", "categoria": "Hardware y Equipos"},
    {"id": 2, "empresa": "SoftLicensing Latam", "contacto": "Ana María Torres", "telefono": "+593 98 211 1222", "categoria": "Software y Licencias"},
    {"id": 3, "empresa": "Redes & Conectividad S.A.", "contacto": "Roberto Silva", "telefono": "+593 99 233 3444", "categoria": "Infraestructura de Red"}
]

FACTURAS = [
    {"num_factura": "FAC-001-00234", "cliente": "Corporación El Sol S.A.", "fecha": "2026-08-10", "monto": 4700.00, "estado": "Pagada"},
    {"num_factura": "FAC-001-00235", "cliente": "Universidad Estatal Amazónica", "fecha": "2026-08-12", "monto": 1200.00, "estado": "Pendiente"},
    {"num_factura": "FAC-001-00236", "cliente": "Proviseguridad Cía. Ltda.", "fecha": "2026-08-15", "monto": 895.50, "estado": "Pagada"}
]

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/productos')
def productos():
    return render_template('productos.html', productos=PRODUCTOS)

@app.route('/clientes')
def clientes():
    return render_template('clientes.html', clientes=CLIENTES)

@app.route('/proveedores')
def proveedores():
    return render_template('proveedores.html', proveedores=PROVEEDORES)

@app.route('/facturacion')
def facturacion():
    return render_template('facturacion.html', facturas=FACTURAS)

if __name__ == '__main__':
    app.run(debug=True)