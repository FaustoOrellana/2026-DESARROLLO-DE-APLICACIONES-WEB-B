from datetime import datetime
from flask import Flask, redirect, render_template, request, url_for

from forms.cliente_form import ClienteForm
from forms.facturacion_form import FacturacionForm
from forms.producto_form import ProductoForm
from forms.proveedor_form import ProveedorForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'techmanager_secret_key_semana11_secure'

SISTEMA_INFO = {
    "nombre_sistema": "TechManager System",
    "periodo": "2026",
    "version": "2.0.0",
    "moneda": "$"
}

# --- DATOS EN MEMORIA ---
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
    return render_template(
        'index.html',
        sistema=SISTEMA_INFO,
        mensaje="panel de control y gestión empresarial",
        total_productos=len(PRODUCTOS),
        total_clientes=len(CLIENTES),
        total_proveedores=len(PROVEEDORES),
        total_facturas=len(FACTURAS)
    )

# --- MÓDULO PRODUCTOS ---
@app.route('/productos')
def productos():
    return render_template('productos.html', productos=PRODUCTOS, sistema=SISTEMA_INFO)

@app.route('/productos/formulario', methods=['GET', 'POST'])
def formulario_producto():
    form = ProductoForm()
    if form.validate_on_submit():
        nuevo_id = max([p['id'] for p in PRODUCTOS], default=0) + 1
        PRODUCTOS.append({
            "id": nuevo_id,
            "nombre": form.nombre.data.strip(),
            "categoria": form.categoria.data,
            "precio": float(form.precio.data),
            "stock": int(form.stock.data)
        })
        return redirect(url_for('productos'))
    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Producto")

@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    producto = next((p for p in PRODUCTOS if p['id'] == id), None)
    if not producto:
        return redirect(url_for('productos'))
    
    form = ProductoForm(data=producto)
    if form.validate_on_submit():
        producto['nombre'] = form.nombre.data.strip()
        producto['categoria'] = form.categoria.data
        producto['precio'] = float(form.precio.data)
        producto['stock'] = int(form.stock.data)
        return redirect(url_for('productos'))
    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Producto")

@app.route('/productos/eliminar/<int:id>')
def eliminar_producto(id):
    global PRODUCTOS
    PRODUCTOS = [p for p in PRODUCTOS if p['id'] != id]
    return redirect(url_for('productos'))

# --- MÓDULO CLIENTES ---
@app.route('/clientes')
def clientes():
    return render_template('clientes.html', clientes=CLIENTES, sistema=SISTEMA_INFO)

@app.route('/clientes/formulario', methods=['GET', 'POST'])
def formulario_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        nuevo_id = max([c['id'] for c in CLIENTES], default=0) + 1
        CLIENTES.append({
            "id": nuevo_id,
            "nombre": form.nombre.data.strip(),
            "ruc": form.ruc.data.strip(),
            "telefono": form.telefono.data.strip(),
            "email": form.email.data.strip().lower()
        })
        return redirect(url_for('clientes'))
    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Cliente")

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    cliente = next((c for c in CLIENTES if c['id'] == id), None)
    if not cliente:
        return redirect(url_for('clientes'))
    
    form = ClienteForm(data=cliente)
    if form.validate_on_submit():
        cliente['nombre'] = form.nombre.data.strip()
        cliente['ruc'] = form.ruc.data.strip()
        cliente['telefono'] = form.telefono.data.strip()
        cliente['email'] = form.email.data.strip().lower()
        return redirect(url_for('clientes'))
    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Cliente")

@app.route('/clientes/eliminar/<int:id>')
def eliminar_cliente(id):
    global CLIENTES
    CLIENTES = [c for c in CLIENTES if c['id'] != id]
    return redirect(url_for('clientes'))

# --- MÓDULO PROVEEDORES ---
@app.route('/proveedores')
def proveedores():
    return render_template('proveedores.html', proveedores=PROVEEDORES, sistema=SISTEMA_INFO)

@app.route('/proveedores/formulario', methods=['GET', 'POST'])
def formulario_proveedor():
    form = ProveedorForm()
    if form.validate_on_submit():
        nuevo_id = max([p['id'] for p in PROVEEDORES], default=0) + 1
        PROVEEDORES.append({
            "id": nuevo_id,
            "nombre": form.nombre.data.strip(),
            "contacto": form.contacto.data.strip(),
            "telefono": form.telefono.data.strip(),
            "categoria": form.categoria.data
        })
        return redirect(url_for('proveedores'))
    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Proveedor")

@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
def editar_proveedor(id):
    proveedor = next((p for p in PROVEEDORES if p['id'] == id), None)
    if not proveedor:
        return redirect(url_for('proveedores'))
    
    form = ProveedorForm(data=proveedor)
    if form.validate_on_submit():
        proveedor['nombre'] = form.nombre.data.strip()
        proveedor['contacto'] = form.contacto.data.strip()
        proveedor['telefono'] = form.telefono.data.strip()
        proveedor['categoria'] = form.categoria.data
        return redirect(url_for('proveedores'))
    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Proveedor")

@app.route('/proveedores/eliminar/<int:id>')
def eliminar_proveedor(id):
    global PROVEEDORES
    PROVEEDORES = [p for p in PROVEEDORES if p['id'] != id]
    return redirect(url_for('proveedores'))

# --- MÓDULO FACTURACIÓN ---
@app.route('/facturacion')
def facturacion():
    return render_template('facturacion.html', facturas=FACTURAS, sistema=SISTEMA_INFO)

@app.route('/facturacion/formulario', methods=['GET', 'POST'])
def formulario_facturacion():
    form = FacturacionForm()
    form.cliente.choices = [('', 'Seleccione un cliente')] + [(c['nombre'], c['nombre']) for c in CLIENTES]
    if form.validate_on_submit():
        FACTURAS.append({
            "numero": form.numero.data.strip().upper(),
            "cliente": form.cliente.data,
            "fecha": str(form.fecha.data),
            "monto": float(form.monto.data),
            "estado": form.estado.data
        })
        return redirect(url_for('facturacion'))
    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura")

@app.route('/facturacion/editar/<numero>', methods=['GET', 'POST'])
def editar_factura(numero):
    factura = next((f for f in FACTURAS if f['numero'] == numero), None)
    if not factura:
        return redirect(url_for('facturacion'))
    
    form = FacturacionForm()
    form.cliente.choices = [('', 'Seleccione un cliente')] + [(c['nombre'], c['nombre']) for c in CLIENTES]
    
    if request.method == 'GET':
        form.numero.data = factura['numero']
        form.cliente.data = factura['cliente']
        form.fecha.data = datetime.strptime(factura['fecha'], '%Y-%m-%d').date() if isinstance(factura['fecha'], str) else factura['fecha']
        form.monto.data = factura['monto']
        form.estado.data = factura['estado']
        
    if form.validate_on_submit():
        factura['numero'] = form.numero.data.strip().upper()
        factura['cliente'] = form.cliente.data
        factura['fecha'] = str(form.fecha.data)
        factura['monto'] = float(form.monto.data)
        factura['estado'] = form.estado.data
        return redirect(url_for('facturacion'))
    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Factura")

@app.route('/facturacion/eliminar/<numero>')
def eliminar_factura(numero):
    global FACTURAS
    FACTURAS = [f for f in FACTURAS if f['numero'] != numero]
    return redirect(url_for('facturacion'))

if __name__ == '__main__':
    app.run(debug=True)