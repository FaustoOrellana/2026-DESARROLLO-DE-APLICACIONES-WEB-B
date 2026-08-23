from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# --- DICCIONARIO ESTRUCTURADO GLOBAL (REQUERIMIENTO SEMANA 10) ---
SISTEMA_INFO = {
    "nombre_sistema": "TechManager System",
    "periodo": "2026",
    "version": "2.0.0",
    "moneda": "$"
}

# --- DATOS DE EJEMPLO EN MEMORIA ---
# Incluye productos con stock disponible y producto con stock 0 para la condición {% if %}
PRODUCTOS = [
    {"id": 1, "nombre": "Servidor Dell PowerEdge R740", "categoria": "Hardware", "precio": 3500.0, "stock": 5},
    {"id": 2, "nombre": "Switch Cisco Catalyst 2960", "categoria": "Redes", "precio": 1200.0, "stock": 0},
    {"id": 3, "nombre": "Licencia Windows Server 2022 Datacenter", "categoria": "Licencias", "precio": 850.0, "stock": 30},
    {"id": 4, "nombre": "Licencia Antivirus Kaspersky Endpoint", "categoria": "Software", "precio": 45.0, "stock": 100},
    {"id": 5, "nombre": "Router Cisco RV340 Gigabit", "categoria": "Redes", "precio": 215.5, "stock": 0}
]

CLIENTES = [
    {"id": 1, "nombre": "Corporación El Sol S.A.", "ruc": "0992345678001", "telefono": "+593 98 123 4567", "email": "contacto@elsol.com"},
    {"id": 2, "nombre": "Universidad Estatal Amazónica", "ruc": "1660001230001", "telefono": "+593 98 885 8100", "email": "info@uea.edu.ec"},
    {"id": 3, "nombre": "Proviseguridad Cía. Ltda.", "ruc": "0791234567001", "telefono": "+593 93 999 8888", "email": "operaciones@proviseguridad.com"}
]

PROVEEDORES = [
    {"id": 1, "nombre": "TechSupply Ecuador", "contacto": "Carlos Mendoza", "telefono": "+593 99 876 5432", "categoria": "Hardware y Equipos"},
    {"id": 2, "nombre": "SoftLicensing Latam", "contacto": "Ana María Torres", "telefono": "+593 98 211 1222", "categoria": "Software y Licencias"},
    {"id": 3, "nombre": "Redes & Conectividad S.A.", "contacto": "Roberto Silva", "telefono": "+593 99 233 3444", "categoria": "Infraestructura de Red"}
]

FACTURAS = [
    {"numero": "FAC-001-00234", "cliente": "Corporación El Sol S.A.", "fecha": "2026-08-10", "monto": 4700.0, "estado": "Pagada"},
    {"numero": "FAC-001-00235", "cliente": "Universidad Estatal Amazónica", "fecha": "2026-08-12", "monto": 1200.0, "estado": "Pendiente"},
    {"numero": "FAC-001-00236", "cliente": "Proviseguridad Cía. Ltda.", "fecha": "2026-08-15", "monto": 895.50, "estado": "Anulada"}
]

# --- RUTA PRINCIPAL ---
@app.route('/')
def inicio():
    # Variable simple enviada hacia el template
    mensaje_bienvenida = "panel de control y gestión empresarial"
    return render_template(
        'index.html',
        sistema=SISTEMA_INFO,
        mensaje=mensaje_bienvenida,
        total_productos=len(PRODUCTOS),
        total_clientes=len(CLIENTES),
        total_proveedores=len(PROVEEDORES),
        total_facturas=len(FACTURAS)
    )

# --- MÓDULO PRODUCTOS ---
@app.route('/productos')
def productos():
    return render_template('productos.html', productos=PRODUCTOS, sistema=SISTEMA_INFO)

@app.route('/productos/agregar', methods=['POST'])
def agregar_producto():
    nuevo_id = max([p['id'] for p in PRODUCTOS], default=0) + 1
    nuevo_item = {
        "id": nuevo_id,
        "nombre": request.form['nombre'],
        "categoria": request.form['categoria'],
        "precio": float(request.form['precio']),
        "stock": int(request.form['stock'])
    }
    PRODUCTOS.append(nuevo_item)
    return redirect(url_for('productos'))

@app.route('/productos/eliminar/<int:id>')
def eliminar_producto(id):
    global PRODUCTOS
    PRODUCTOS = [p for p in PRODUCTOS if p['id'] != id]
    return redirect(url_for('productos'))

# --- MÓDULO CLIENTES ---
@app.route('/clientes')
def clientes():
    return render_template('clientes.html', clientes=CLIENTES, sistema=SISTEMA_INFO)

@app.route('/clientes/agregar', methods=['POST'])
def agregar_cliente():
    nuevo_id = max([c['id'] for c in CLIENTES], default=0) + 1
    CLIENTES.append({
        "id": nuevo_id,
        "nombre": request.form['nombre'],
        "ruc": request.form['ruc'],
        "telefono": request.form['telefono'],
        "email": request.form['email']
    })
    return redirect(url_for('clientes'))

@app.route('/clientes/eliminar/<int:id>')
def eliminar_cliente(id):
    global CLIENTES
    CLIENTES = [c for c in CLIENTES if c['id'] != id]
    return redirect(url_for('clientes'))

# --- MÓDULO PROVEEDORES ---
@app.route('/proveedores')
def proveedores():
    return render_template('proveedores.html', proveedores=PROVEEDORES, sistema=SISTEMA_INFO)

@app.route('/proveedores/agregar', methods=['POST'])
def agregar_proveedor():
    nuevo_id = max([p['id'] for p in PROVEEDORES], default=0) + 1
    PROVEEDORES.append({
        "id": nuevo_id,
        "nombre": request.form['nombre'],
        "contacto": request.form['contacto'],
        "telefono": request.form['telefono'],
        "categoria": request.form['categoria']
    })
    return redirect(url_for('proveedores'))

@app.route('/proveedores/eliminar/<int:id>')
def eliminar_proveedor(id):
    global PROVEEDORES
    PROVEEDORES = [pr for pr in PROVEEDORES if pr['id'] != id]
    return redirect(url_for('proveedores'))

# --- MÓDULO FACTURACIÓN ---
@app.route('/facturacion')
def facturacion():
    return render_template('facturacion.html', facturas=FACTURAS, sistema=SISTEMA_INFO)

@app.route('/facturacion/agregar', methods=['POST'])
def agregar_factura():
    FACTURAS.append({
        "numero": request.form['numero'],
        "cliente": request.form['cliente'],
        "fecha": request.form['fecha'],
        "monto": float(request.form['monto']),
        "estado": request.form['estado']
    })
    return redirect(url_for('facturacion'))

@app.route('/facturacion/eliminar/<string:numero>')
def eliminar_factura(numero):
    global FACTURAS
    FACTURAS = [f for f in FACTURAS if f['numero'] != numero]
    return redirect(url_for('facturacion'))

if __name__ == '__main__':
    app.run(debug=True)