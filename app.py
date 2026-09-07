import os
import sqlite3
from datetime import datetime
from flask import Flask, redirect, render_template, request, url_for, flash

from forms.cliente_form import ClienteForm
from forms.facturacion_form import FacturacionForm
from forms.producto_form import ProductoForm
from forms.proveedor_form import ProveedorForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'techmanager_secret_key_semana11_secure'

# CONFIGURACIÓN SQLITE Y CREACIÓN DE LAS 4 TABLAS
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'techmanager.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Tabla Productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    ''')

    # 2. Tabla Clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            ruc TEXT NOT NULL UNIQUE,
            telefono TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')

    # 3. Tabla Proveedores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            contacto TEXT NOT NULL,
            telefono TEXT NOT NULL,
            categoria TEXT NOT NULL
        )
    ''')

    # 4. Tabla Facturas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            cliente TEXT NOT NULL,
            fecha TEXT NOT NULL,
            monto REAL NOT NULL,
            estado TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

# Inicialización obligatoria
init_db()

# INFORMACIÓN DEL SISTEMA
SISTEMA_INFO = {
    "nombre_sistema": "TechManager System",
    "periodo": "2026",
    "version": "2.0.0",
    "moneda": "$"
}

# RUTA PRINCIPAL
@app.route('/')
def inicio():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM productos')
    total_prod = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM clientes')
    total_cli = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM proveedores')
    total_prov = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM facturas')
    total_fac = cursor.fetchone()[0]
    
    conn.close()

    return render_template(
        'index.html',
        sistema=SISTEMA_INFO,
        mensaje="panel de control y gestión empresarial",
        total_productos=total_prod,
        total_clientes=total_cli,
        total_proveedores=total_prov,
        total_facturas=total_fac
    )

# MÓDULO PRODUCTOS 
@app.route('/productos')
def productos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, categoria, precio, stock FROM productos ORDER BY id DESC')
    productos_db = cursor.fetchall()
    conn.close()
    return render_template('productos.html', productos=productos_db, sistema=SISTEMA_INFO)

@app.route('/productos/formulario', methods=['GET', 'POST'])
def formulario_producto():
    form = ProductoForm()
    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        categoria = form.categoria.data if hasattr(form, 'categoria') and form.categoria.data else 'General'
        precio = float(form.precio.data)
        stock = int(form.stock.data)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO productos (nombre, categoria, precio, stock)
            VALUES (?, ?, ?, ?)
        ''', (nombre, categoria, precio, stock))
        conn.commit()
        conn.close()

        return redirect(url_for('productos'))
    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Producto")

@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM productos WHERE id = ?', (id,))
    producto = cursor.fetchone()
    conn.close()

    if not producto:
        return redirect(url_for('productos'))

    form = ProductoForm()
    if request.method == 'GET':
        form.nombre.data = producto['nombre']
        if hasattr(form, 'categoria'):
            form.categoria.data = producto['categoria']
        form.precio.data = producto['precio']
        form.stock.data = producto['stock']

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        categoria = form.categoria.data if hasattr(form, 'categoria') and form.categoria.data else 'General'
        precio = float(form.precio.data)
        stock = int(form.stock.data)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE productos 
            SET nombre = ?, categoria = ?, precio = ?, stock = ?
            WHERE id = ?
        ''', (nombre, categoria, precio, stock, id))
        conn.commit()
        conn.close()

        return redirect(url_for('productos'))
    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Producto")

@app.route('/productos/eliminar/<int:id>')
def eliminar_producto(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM productos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('productos'))

# MÓDULO CLIENTES
@app.route('/clientes')
def clientes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, ruc, telefono, email FROM clientes ORDER BY id DESC')
    clientes_db = cursor.fetchall()
    conn.close()
    return render_template('clientes.html', clientes=clientes_db, sistema=SISTEMA_INFO)

@app.route('/clientes/formulario', methods=['GET', 'POST'])
def formulario_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        ruc = form.ruc.data.strip()
        telefono = form.telefono.data.strip()
        email = form.email.data.strip().lower()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO clientes (nombre, ruc, telefono, email)
                VALUES (?, ?, ?, ?)
            ''', (nombre, ruc, telefono, email))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash('Error: El RUC ingresado ya existe.', 'danger')
            return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Cliente")
        finally:
            conn.close()
            
        return redirect(url_for('clientes'))
    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Cliente")

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes WHERE id = ?', (id,))
    cliente = cursor.fetchone()
    conn.close()

    if not cliente:
        return redirect(url_for('clientes'))
    
    form = ClienteForm(data=dict(cliente))
    
    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        ruc = form.ruc.data.strip()
        telefono = form.telefono.data.strip()
        email = form.email.data.strip().lower()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE clientes 
                SET nombre = ?, ruc = ?, telefono = ?, email = ?
                WHERE id = ?
            ''', (nombre, ruc, telefono, email, id))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash('Error: El RUC ingresado ya pertenece a otro cliente.', 'danger')
            return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Cliente")
        finally:
            conn.close()
            
        return redirect(url_for('clientes'))
    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Cliente")

@app.route('/clientes/eliminar/<int:id>')
def eliminar_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clientes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('clientes'))

# --- MÓDULO PROVEEDORES ---
@app.route('/proveedores')
def proveedores():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, contacto, telefono, categoria FROM proveedores ORDER BY id DESC')
    proveedores_db = cursor.fetchall()
    conn.close()
    return render_template('proveedores.html', proveedores=proveedores_db, sistema=SISTEMA_INFO)

@app.route('/proveedores/formulario', methods=['GET', 'POST'])
def formulario_proveedor():
    form = ProveedorForm()
    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        contacto = form.contacto.data.strip()
        telefono = form.telefono.data.strip()
        categoria = form.categoria.data
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO proveedores (nombre, contacto, telefono, categoria)
            VALUES (?, ?, ?, ?)
        ''', (nombre, contacto, telefono, categoria))
        conn.commit()
        conn.close()
        
        return redirect(url_for('proveedores'))
    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Proveedor")

@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
def editar_proveedor(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM proveedores WHERE id = ?', (id,))
    proveedor = cursor.fetchone()
    conn.close()

    if not proveedor:
        return redirect(url_for('proveedores'))
    
    form = ProveedorForm(data=dict(proveedor))
    
    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        contacto = form.contacto.data.strip()
        telefono = form.telefono.data.strip()
        categoria = form.categoria.data
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE proveedores 
            SET nombre = ?, contacto = ?, telefono = ?, categoria = ?
            WHERE id = ?
        ''', (nombre, contacto, telefono, categoria, id))
        conn.commit()
        conn.close()
        
        return redirect(url_for('proveedores'))
    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Proveedor")

@app.route('/proveedores/eliminar/<int:id>')
def eliminar_proveedor(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM proveedores WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('proveedores'))

# MÓDULO FACTURACIÓN
@app.route('/facturacion')
def facturacion():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, numero, cliente, fecha, monto, estado FROM facturas ORDER BY id DESC')
    facturas_db = cursor.fetchall()
    conn.close()
    return render_template('facturacion.html', facturas=facturas_db, sistema=SISTEMA_INFO)

@app.route('/facturacion/formulario', methods=['GET', 'POST'])
def formulario_facturacion():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT nombre FROM clientes ORDER BY nombre ASC')
    clientes_bd = cursor.fetchall()
    conn.close()

    form = FacturacionForm()
    form.cliente.choices = [('', 'Seleccione un cliente')] + [(c['nombre'], c['nombre']) for c in clientes_bd]
    
    if form.validate_on_submit():
        numero = form.numero.data.strip().upper()
        cliente = form.cliente.data
        fecha = str(form.fecha.data)
        monto = float(form.monto.data)
        estado = form.estado.data
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO facturas (numero, cliente, fecha, monto, estado)
                VALUES (?, ?, ?, ?, ?)
            ''', (numero, cliente, fecha, monto, estado))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash('Error: El número de factura ya existe.', 'danger')
            return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura")
        finally:
            conn.close()
            
        return redirect(url_for('facturacion'))
    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura")

@app.route('/facturacion/editar/<numero>', methods=['GET', 'POST'])
def editar_factura(numero):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM facturas WHERE numero = ?', (numero,))
    factura = cursor.fetchone()
    
    cursor.execute('SELECT nombre FROM clientes ORDER BY nombre ASC')
    clientes_bd = cursor.fetchall()
    conn.close()

    if not factura:
        return redirect(url_for('facturacion'))
    
    form = FacturacionForm()
    form.cliente.choices = [('', 'Seleccione un cliente')] + [(c['nombre'], c['nombre']) for c in clientes_bd]
    
    if request.method == 'GET':
        form.numero.data = factura['numero']
        form.cliente.data = factura['cliente']
        # Convertimos el string de la fecha (YYYY-MM-DD) a objeto date para WTForms
        form.fecha.data = datetime.strptime(factura['fecha'], '%Y-%m-%d').date()
        form.monto.data = factura['monto']
        form.estado.data = factura['estado']
        
    if form.validate_on_submit():
        nuevo_numero = form.numero.data.strip().upper()
        cliente = form.cliente.data
        fecha = str(form.fecha.data)
        monto = float(form.monto.data)
        estado = form.estado.data
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE facturas 
                SET numero = ?, cliente = ?, fecha = ?, monto = ?, estado = ?
                WHERE numero = ?
            ''', (nuevo_numero, cliente, fecha, monto, estado, numero))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash('Error: El nuevo número de factura ya está en uso.', 'danger')
            return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Factura")
        finally:
            conn.close()
            
        return redirect(url_for('facturacion'))
    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Factura")

@app.route('/facturacion/eliminar/<numero>')
def eliminar_factura(numero):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM facturas WHERE numero = ?', (numero,))
    conn.commit()
    conn.close()
    return redirect(url_for('facturacion'))

if __name__ == '__main__':
    app.run(debug=True)