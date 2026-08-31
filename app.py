from flask import Flask, render_template, request, redirect, url_for, flash

# Importaciones directas por archivo desde la carpeta forms
from forms.producto_form import ProductoForm
from forms.cliente_form import ClienteForm
from forms.proveedor_form import ProveedorForm
from forms.facturacion_form import FacturacionForm

app = Flask(__name__)
# Clave obligatoria para el funcionamiento del token CSRF
app.config['SECRET_KEY'] = 'techmanager_secret_key_semana11_secure'

# --- DICCIONARIO ESTRUCTURADO GLOBAL ---
SISTEMA_INFO = {
    "nombre_sistema": "TechManager System",
    "periodo": "2026",
    "version": "2.0.0",
    "moneda": "$"
}

# --- DATOS DE EJEMPLO EN MEMORIA ---
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

@app.route('/productos/formulario', methods=['GET', 'POST'])
def formulario_producto():
    form = ProductoForm()
    if form.validate_on_submit():
        nombre_limpio = form.nombre.data.strip()
        # Validación contra productos duplicados
        if any(p['nombre'].strip().lower() == nombre_limpio.lower() for p in PRODUCTOS):
            form.nombre.errors.append('Ya existe un producto registrado con este nombre.')
            return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Producto")

        nuevo_id = max([p['id'] for p in PRODUCTOS], default=0) + 1
        nuevo_item = {
            "id": nuevo_id,
            "nombre": nombre_limpio,
            "categoria": form.categoria.data,
            "precio": float(form.precio.data),
            "stock": int(form.stock.data)
        }
        PRODUCTOS.append(nuevo_item)
        return redirect(url_for('productos'))
    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Producto")

# --- MÓDULO CLIENTES ---
@app.route('/clientes')
def clientes():
    return render_template('clientes.html', clientes=CLIENTES, sistema=SISTEMA_INFO)

@app.route('/clientes/formulario', methods=['GET', 'POST'])
def formulario_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        ruc_limpio = form.ruc.data.strip()
        # Validación contra identificación / RUC duplicado
        if any(c['ruc'].strip() == ruc_limpio for c in CLIENTES):
            form.ruc.errors.append('Ya existe un cliente registrado con este RUC o Cédula.')
            return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Cliente")

        nuevo_id = max([c['id'] for c in CLIENTES], default=0) + 1
        nuevo_item = {
            "id": nuevo_id,
            "nombre": form.nombre.data.strip(),
            "ruc": ruc_limpio,
            "telefono": form.telefono.data.strip(),
            "email": form.email.data.strip().lower()
        }
        CLIENTES.append(nuevo_item)
        return redirect(url_for('clientes'))
    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Cliente")

# --- MÓDULO PROVEEDORES ---
@app.route('/proveedores')
def proveedores():
    return render_template('proveedores.html', proveedores=PROVEEDORES, sistema=SISTEMA_INFO)

@app.route('/proveedores/formulario', methods=['GET', 'POST'])
def formulario_proveedor():
    form = ProveedorForm()
    if form.validate_on_submit():
        empresa_limpia = form.nombre.data.strip()
        # Validación contra proveedores con el mismo nombre
        if any(pr['nombre'].strip().lower() == empresa_limpia.lower() for pr in PROVEEDORES):
            form.nombre.errors.append('Ya existe un proveedor registrado con este nombre de empresa.')
            return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Proveedor")

        nuevo_id = max([p['id'] for p in PROVEEDORES], default=0) + 1
        nuevo_item = {
            "id": nuevo_id,
            "nombre": empresa_limpia,
            "contacto": form.contacto.data.strip(),
            "telefono": form.telefono.data.strip(),
            "categoria": form.categoria.data
        }
        PROVEEDORES.append(nuevo_item)
        return redirect(url_for('proveedores'))
    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Proveedor")

# --- MÓDULO FACTURACIÓN ---
@app.route('/facturacion')
def facturacion():
    return render_template('facturacion.html', facturas=FACTURAS, sistema=SISTEMA_INFO)

@app.route('/facturacion/formulario', methods=['GET', 'POST'])
def formulario_facturacion():
    form = FacturacionForm()
    # Carga dinámica de clientes en memoria para el SelectField
    form.cliente.choices = [('', 'Seleccione un cliente')] + [(c['nombre'], c['nombre']) for c in CLIENTES]
    
    if form.validate_on_submit():
        numero_factura = form.numero.data.strip().upper()
        # Validación contra comprobantes duplicados
        if any(f['numero'].strip().upper() == numero_factura for f in FACTURAS):
            form.numero.errors.append('Este número de factura ya se encuentra registrado.')
            return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura")

        nueva_factura = {
            "numero": numero_factura,
            "cliente": form.cliente.data,
            "fecha": str(form.fecha.data),
            "monto": float(form.monto.data),
            "estado": form.estado.data
        }
        FACTURAS.append(nueva_factura)
        return redirect(url_for('facturacion'))
    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura")

if __name__ == '__main__':
    app.run(debug=True)