import os
from datetime import datetime
from flask import Flask, redirect, render_template, request, url_for, flash

from forms.cliente_form import ClienteForm
from forms.facturacion_form import FacturacionForm
from forms.producto_form import ProductoForm
from forms.proveedor_form import ProveedorForm

# Conexión centralizada con PostgreSQL
from conexion.conexion import obtener_conexion

app = Flask(__name__)
app.config['SECRET_KEY'] = 'techmanager_secret_key_semana11_secure'

SISTEMA_INFO = {
    "nombre_sistema": "TechManager System",
    "periodo": "2026",
    "version": "2.0.0",
    "moneda": "$"
}

@app.route('/')
def inicio():
    conn = obtener_conexion()
    total_prod = total_cli = total_prov = total_fac = 0

    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) AS total FROM productos;')
            total_prod = cursor.fetchone()['total']

            cursor.execute('SELECT COUNT(*) AS total FROM clientes;')
            total_cli = cursor.fetchone()['total']

            cursor.execute('SELECT COUNT(*) AS total FROM proveedores;')
            total_prov = cursor.fetchone()['total']

            cursor.execute('SELECT COUNT(*) AS total FROM facturas;')
            total_fac = cursor.fetchone()['total']
            cursor.close()
        finally:
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

# MÓDULO 1: PRODUCTOS

# 1. LISTADO (SELECT con JOIN y fetchall)
@app.route('/productos')
def productos():
    conn = obtener_conexion()
    productos_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.nombre, c.nombre AS categoria, p.precio, p.stock
                FROM productos p
                INNER JOIN categorias c ON p.id_categoria = c.id
                ORDER BY p.id DESC;
            ''')
            productos_db = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template('productos.html', productos=productos_db, sistema=SISTEMA_INFO)

# 2. AGREGAR (INSERT INTO parametrizado con commit)
@app.route('/productos/formulario', methods=['GET', 'POST'])
def formulario_producto():
    form = ProductoForm()

    conn = obtener_conexion()
    categorias = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
            categorias = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices') and categorias:
        form.categoria.choices = [(str(c['id']), c['nombre']) for c in categorias]

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        precio = float(form.precio.data)
        stock = int(form.stock.data)
        id_categoria = int(form.categoria.data) if hasattr(form, 'categoria') and form.categoria.data and str(form.categoria.data).isdigit() else 1

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO productos (nombre, precio, stock, id_categoria, id_marca)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (nombre, precio, stock, id_categoria, 1))
                conn.commit()
                cursor.close()
                flash('Producto registrado correctamente.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar el producto: {e}', 'danger')
            finally:
                conn.close()

            return redirect(url_for('productos'))

    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Producto")

# 3. MODIFICAR (SELECT WHERE para cargar y UPDATE WHERE con commit)
@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('productos'))

    producto = None
    categorias = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM productos WHERE id = %s;', (id,))
        producto = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
        categorias = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    if not producto:
        flash('El producto solicitado no existe.', 'warning')
        return redirect(url_for('productos'))

    form = ProductoForm()
    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices') and categorias:
        form.categoria.choices = [(str(c['id']), c['nombre']) for c in categorias]

    if request.method == 'GET':
        form.nombre.data = producto['nombre']
        form.precio.data = producto['precio']
        form.stock.data = producto['stock']
        if hasattr(form, 'categoria'):
            form.categoria.data = str(producto['id_categoria'])

    elif form.validate_on_submit():
        nombre = form.nombre.data.strip()
        precio = float(form.precio.data)
        stock = int(form.stock.data)
        id_categoria = int(form.categoria.data) if hasattr(form, 'categoria') and form.categoria.data and str(form.categoria.data).isdigit() else producto['id_categoria']

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE productos 
                    SET nombre = %s, precio = %s, stock = %s, id_categoria = %s
                    WHERE id = %s;
                ''', (nombre, precio, stock, id_categoria, id))
                conn.commit()
                cursor.close()
                flash('Producto modificado exitosamente.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error al modificar el producto: {e}', 'danger')
            finally:
                conn.close()

            return redirect(url_for('productos'))

    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Producto")

# 4. ELIMINAR (DELETE WHERE con commit)
@app.route('/productos/eliminar/<int:id>', methods=['GET', 'POST'])
def eliminar_producto(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM productos WHERE id = %s;', (id,))
            conn.commit()
            cursor.close()
            flash('Producto eliminado satisfactoriamente.', 'info')
        except Exception as e:
            conn.rollback()
            flash(f'No se puede eliminar el producto (está referenciado en detalle de facturas): {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('productos'))

# MÓDULO 2: CLIENTES

# 1. LISTADO (SELECT y fetchall)
@app.route('/clientes')
def clientes():
    conn = obtener_conexion()
    clientes_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre, ruc, telefono, email FROM clientes ORDER BY id DESC;')
            clientes_db = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()
    return render_template('clientes.html', clientes=clientes_db, sistema=SISTEMA_INFO)

# 2. AGREGAR (INSERT INTO parametrizado con commit)
@app.route('/clientes/formulario', methods=['GET', 'POST'])
def formulario_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        ruc = form.ruc.data.strip()
        telefono = form.telefono.data.strip()
        email = form.email.data.strip().lower()

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO clientes (nombre, ruc, telefono, email, id_ciudad)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (nombre, ruc, telefono, email, 1))
                conn.commit()
                cursor.close()
                flash('Cliente registrado correctamente.', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                conn.rollback()
                flash('Error: El RUC ingresado ya existe o los datos son inválidos.', 'danger')
            finally:
                conn.close()

    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Cliente")

# 3. MODIFICAR (SELECT WHERE para cargar y UPDATE WHERE con commit)
@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('clientes'))

    cliente = None
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM clientes WHERE id = %s;', (id,))
        cliente = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if not cliente:
        flash('El cliente solicitado no existe.', 'warning')
        return redirect(url_for('clientes'))

    form = ClienteForm(data=dict(cliente))

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        ruc = form.ruc.data.strip()
        telefono = form.telefono.data.strip()
        email = form.email.data.strip().lower()

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE clientes
                    SET nombre = %s, ruc = %s, telefono = %s, email = %s
                    WHERE id = %s;
                ''', (nombre, ruc, telefono, email, id))
                conn.commit()
                cursor.close()
                flash('Cliente actualizado correctamente.', 'success')
                return redirect(url_for('clientes'))
            except Exception:
                conn.rollback()
                flash('Error: El RUC ingresado ya pertenece a otro cliente.', 'danger')
            finally:
                conn.close()

    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Cliente")

# 4. ELIMINAR (DELETE WHERE con commit)
@app.route('/clientes/eliminar/<int:id>', methods=['GET', 'POST'])
def eliminar_cliente(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM clientes WHERE id = %s;', (id,))
            conn.commit()
            cursor.close()
            flash('Cliente eliminado correctamente.', 'info')
        except Exception as e:
            conn.rollback()
            flash(f'No se puede eliminar el cliente (tiene facturas asociadas): {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('clientes'))

# MÓDULO 3: PROVEEDORES

# 1. LISTADO (SELECT con JOIN y fetchall)
@app.route('/proveedores')
def proveedores():
    conn = obtener_conexion()
    proveedores_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.nombre, p.contacto, p.telefono, c.nombre AS categoria 
                FROM proveedores p
                INNER JOIN categorias c ON p.id_categoria = c.id
                ORDER BY p.id DESC;
            ''')
            proveedores_db = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()
    return render_template('proveedores.html', proveedores=proveedores_db, sistema=SISTEMA_INFO)

# 2. AGREGAR (INSERT INTO parametrizado con commit)
@app.route('/proveedores/formulario', methods=['GET', 'POST'])
def formulario_proveedor():
    form = ProveedorForm()

    conn = obtener_conexion()
    categorias = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
            categorias = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices') and categorias:
        form.categoria.choices = [(str(c['id']), c['nombre']) for c in categorias]

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        contacto = form.contacto.data.strip()
        telefono = form.telefono.data.strip()
        id_categoria = int(form.categoria.data) if hasattr(form, 'categoria') and form.categoria.data and str(form.categoria.data).isdigit() else 1

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO proveedores (nombre, contacto, telefono, id_categoria, id_ciudad)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (nombre, contacto, telefono, id_categoria, 1))
                conn.commit()
                cursor.close()
                flash('Proveedor registrado correctamente.', 'success')
                return redirect(url_for('proveedores'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar el proveedor: {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Proveedor")

# 3. MODIFICAR (SELECT WHERE para cargar y UPDATE WHERE con commit)
@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
def editar_proveedor(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('proveedores'))

    proveedor = None
    categorias = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM proveedores WHERE id = %s;', (id,))
        proveedor = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
        categorias = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    if not proveedor:
        flash('El proveedor solicitado no existe.', 'warning')
        return redirect(url_for('proveedores'))

    form = ProveedorForm()
    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices') and categorias:
        form.categoria.choices = [(str(c['id']), c['nombre']) for c in categorias]

    if request.method == 'GET':
        form.nombre.data = proveedor['nombre']
        form.contacto.data = proveedor['contacto']
        form.telefono.data = proveedor['telefono']
        if hasattr(form, 'categoria'):
            form.categoria.data = str(proveedor['id_categoria'])

    elif form.validate_on_submit():
        nombre = form.nombre.data.strip()
        contacto = form.contacto.data.strip()
        telefono = form.telefono.data.strip()
        id_categoria = int(form.categoria.data) if hasattr(form, 'categoria') and form.categoria.data and str(form.categoria.data).isdigit() else proveedor['id_categoria']

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE proveedores 
                    SET nombre = %s, contacto = %s, telefono = %s, id_categoria = %s
                    WHERE id = %s;
                ''', (nombre, contacto, telefono, id_categoria, id))
                conn.commit()
                cursor.close()
                flash('Proveedor actualizado exitosamente.', 'success')
                return redirect(url_for('proveedores'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al actualizar: {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Proveedor")

# 4. ELIMINAR (DELETE WHERE con commit)
@app.route('/proveedores/eliminar/<int:id>', methods=['GET', 'POST'])
def eliminar_proveedor(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM proveedores WHERE id = %s;', (id,))
            conn.commit()
            cursor.close()
            flash('Proveedor eliminado satisfactoriamente.', 'info')
        except Exception as e:
            conn.rollback()
            flash(f'No se puede eliminar el proveedor: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('proveedores'))

# MÓDULO 4: FACTURACIÓN

# 1. LISTADO (SELECT con múltiples JOINs y fetchall)
@app.route('/facturacion')
def facturacion():
    conn = obtener_conexion()
    facturas_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.numero, c.nombre AS cliente, f.fecha, f.monto, e.nombre AS estado
                FROM facturas f
                INNER JOIN clientes c ON f.id_cliente = c.id
                INNER JOIN estados_factura e ON f.id_estado = e.id
                ORDER BY f.id DESC;
            ''')
            facturas_db = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()
    return render_template('facturacion.html', facturas=facturas_db, sistema=SISTEMA_INFO)

# 2. AGREGAR (INSERT INTO parametrizado con commit)
@app.route('/facturacion/formulario', methods=['GET', 'POST'])
def formulario_facturacion():
    conn = obtener_conexion()
    clientes_bd = []
    estados_bd = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre FROM clientes ORDER BY nombre ASC;')
            clientes_bd = cursor.fetchall()
            cursor.execute('SELECT id, nombre FROM estados_factura ORDER BY id ASC;')
            estados_bd = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

    form = FacturacionForm()
    # Soporta tanto si form.cliente espera el nombre o el ID
    if hasattr(form, 'cliente') and hasattr(form.cliente, 'choices'):
        form.cliente.choices = [('', 'Seleccione un cliente')] + [(str(c['id']), c['nombre']) for c in clientes_bd]

    if form.validate_on_submit():
        numero = form.numero.data.strip().upper()
        fecha = str(form.fecha.data)
        monto = float(form.monto.data)
        
        # Resolver ID del cliente
        cliente_input = str(form.cliente.data).strip()
        id_cliente = int(cliente_input) if cliente_input.isdigit() else 1
        if not cliente_input.isdigit():
            for c in clientes_bd:
                if c['nombre'] == cliente_input:
                    id_cliente = c['id']
                    break

        # Resolver ID de estado ('Pagada', 'Pendiente', etc.)
        estado_input = getattr(form, 'estado', None)
        id_estado = 1
        if estado_input and estado_input.data:
            val_estado = str(estado_input.data).strip().capitalize()
            for e in estados_bd:
                if e['nombre'] == val_estado or str(e['id']) == val_estado:
                    id_estado = e['id']
                    break

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago)
                    VALUES (%s, %s, %s, %s, %s, %s);
                ''', (numero, fecha, monto, id_cliente, id_estado, 1))
                conn.commit()
                cursor.close()
                flash('Factura registrada con éxito.', 'success')
                return redirect(url_for('facturacion'))
            except Exception as e:
                conn.rollback()
                flash(f'Error: El número de factura ya existe o los datos son inválidos ({e}).', 'danger')
            finally:
                conn.close()

    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura")

# 3. MODIFICAR (SELECT WHERE para cargar y UPDATE WHERE con commit)
@app.route('/facturacion/editar/<numero>', methods=['GET', 'POST'])
def editar_factura(numero):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('facturacion'))

    factura = None
    clientes_bd = []
    estados_bd = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM facturas WHERE numero = %s;', (numero,))
        factura = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM clientes ORDER BY nombre ASC;')
        clientes_bd = cursor.fetchall()
        cursor.execute('SELECT id, nombre FROM estados_factura ORDER BY id ASC;')
        estados_bd = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    if not factura:
        flash('Factura no encontrada.', 'warning')
        return redirect(url_for('facturacion'))

    form = FacturacionForm()
    if hasattr(form, 'cliente') and hasattr(form.cliente, 'choices'):
        form.cliente.choices = [('', 'Seleccione un cliente')] + [(str(c['id']), c['nombre']) for c in clientes_bd]

    if request.method == 'GET':
        form.numero.data = factura['numero']
        form.fecha.data = factura['fecha'] if hasattr(factura['fecha'], 'year') else datetime.strptime(str(factura['fecha']), '%Y-%m-%d').date()
        form.monto.data = factura['monto']
        if hasattr(form, 'cliente'):
            form.cliente.data = str(factura['id_cliente'])
        if hasattr(form, 'estado'):
            for e in estados_bd:
                if e['id'] == factura['id_estado']:
                    form.estado.data = e['nombre']
                    break

    elif form.validate_on_submit():
        nuevo_numero = form.numero.data.strip().upper()
        fecha = str(form.fecha.data)
        monto = float(form.monto.data)

        cliente_input = str(form.cliente.data).strip()
        id_cliente = int(cliente_input) if cliente_input.isdigit() else factura['id_cliente']
        if not cliente_input.isdigit():
            for c in clientes_bd:
                if c['nombre'] == cliente_input:
                    id_cliente = c['id']
                    break

        estado_input = getattr(form, 'estado', None)
        id_estado = factura['id_estado']
        if estado_input and estado_input.data:
            val_estado = str(estado_input.data).strip().capitalize()
            for e in estados_bd:
                if e['nombre'] == val_estado or str(e['id']) == val_estado:
                    id_estado = e['id']
                    break

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE facturas
                    SET numero = %s, fecha = %s, monto = %s, id_cliente = %s, id_estado = %s
                    WHERE numero = %s;
                ''', (nuevo_numero, fecha, monto, id_cliente, id_estado, numero))
                conn.commit()
                cursor.close()
                flash('Factura actualizada correctamente.', 'success')
                return redirect(url_for('facturacion'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al modificar la factura: {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Factura")

# 4. ELIMINAR (DELETE WHERE con commit)
@app.route('/facturacion/eliminar/<numero>', methods=['GET', 'POST'])
def eliminar_factura(numero):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM facturas WHERE numero = %s;', (numero,))
            conn.commit()
            cursor.close()
            flash('Factura eliminada satisfactoriamente.', 'info')
        except Exception as e:
            conn.rollback()
            flash(f'No se pudo eliminar la factura: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('facturacion'))

if __name__ == '__main__':
    app.run(debug=True)