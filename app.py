import os
import io
import random
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, request, url_for, flash, session, send_file

# IMPORTACIONES DE AUTENTICACIÓN
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Generador de imagen CAPTCHA
from captcha.image import ImageCaptcha

# Modelo de Usuario desacoplado
from models import Usuario

# Formularios del sistema + Formularios de autenticación
from forms.cliente_form import ClienteForm
from forms.facturacion_form import FacturacionForm
from forms.producto_form import ProductoForm
from forms.proveedor_form import ProveedorForm
from forms.usuario_form import UsuarioForm
from forms.login_form import LoginForm

# Conexión centralizada con PostgreSQL
from conexion.conexion import obtener_conexion

from flask_wtf.csrf import CSRFProtect  # <-- Importar

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'techmanager_dev_fallback_key_2026')

csrf = CSRFProtect(app)  # <-- Inicializar CSRFProtect globalmente

# --- CONFIGURACIÓN FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Debe iniciar sesión para acceder a esta sección.'
login_manager.login_message_category = 'warning'

# Recupera el usuario desde PostgreSQL por su identificador
@login_manager.user_loader
def load_user(user_id):
    conn = obtener_conexion()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, password, rol FROM usuarios WHERE id = %s;", (int(user_id),))
        u = cursor.fetchone()
        cursor.close()
        if u:
            rol_db = u.get('rol') if isinstance(u, dict) else u[3]
            usuario_db = u.get('usuario') if isinstance(u, dict) else u[1]
            pass_db = u.get('password') if isinstance(u, dict) else u[2]
            id_db = u.get('id') if isinstance(u, dict) else u[0]
            return Usuario(id=id_db, usuario=usuario_db, password=pass_db, rol=rol_db or 'usuario')
    except Exception:
        return None
    finally:
        conn.close()
    return None

# --- DECORADOR PARA RESTRINGIR POR ROLES ---
def roles_requeridos(*roles_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debe iniciar sesión para acceder a esta sección.', 'warning')
                return redirect(url_for('login'))
            if not current_user.tiene_rol(*roles_permitidos):
                flash('Acceso denegado: No tiene permisos suficientes para realizar esta acción.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

SISTEMA_INFO = {
    "nombre_sistema": "TechManager System",
    "periodo": "2026",
    "version": "2.0.0",
    "moneda": "$"
}

# --- FUNCIÓN AUXILIAR REUTILIZABLE DE CONTEOS ---
def obtener_metricas_globales():
    """Consulta los conteos en PostgreSQL de forma resiliente a tipos de cursor."""
    metricas = {
        'total_productos': 0,
        'total_clientes': 0,
        'total_proveedores': 0,
        'total_facturas': 0
    }
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            def contar(tabla):
                cursor.execute(f'SELECT COUNT(*) AS total FROM {tabla};')
                res = cursor.fetchone()
                if not res:
                    return 0
                return res['total'] if isinstance(res, dict) else res[0]

            metricas['total_productos'] = contar('productos')
            metricas['total_clientes'] = contar('clientes')
            metricas['total_proveedores'] = contar('proveedores')
            metricas['total_facturas'] = contar('facturas')
            cursor.close()
        except Exception:
            pass
        finally:
            conn.close()
    return metricas

# --- GENERACIÓN DE CAPTCHA DINÁMICO ---
def generar_texto_captcha(longitud=5):
    caracteres = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return ''.join(random.choices(caracteres, k=longitud))

@app.route('/captcha-image')
def captcha_image():
    image = ImageCaptcha(width=180, height=60)
    texto = generar_texto_captcha()
    session['captcha_text'] = texto
    data = image.generate(texto)
    return send_file(io.BytesIO(data.getvalue()), mimetype='image/png')

# --- RUTA DE REGISTRO ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = UsuarioForm()
    if form.validate_on_submit():
        captcha_ingresado = getattr(form, 'captcha', None)
        captcha_valor = captcha_ingresado.data.strip().upper() if captcha_ingresado else request.form.get('captcha', '').strip().upper()
        captcha_guardado = session.get('captcha_text', '')

        if not captcha_valor or captcha_valor != captcha_guardado:
            flash('Código de seguridad CAPTCHA incorrecto. Intente nuevamente.', 'danger')
            return render_template('registro.html', form=form, sistema=SISTEMA_INFO)

        session.pop('captcha_text', None)

        nombre_usuario = form.usuario.data.strip()
        email_usuario = form.email.data.strip().lower()
        hash_password = generate_password_hash(form.password.data)

        # Capturar ruc si existe en el formulario, o None si viene vacío
        ruc_campo = getattr(form, 'ruc', None)
        ruc_valor = ruc_campo.data.strip() if ruc_campo and ruc_campo.data else request.form.get('ruc', '').strip()
        ruc_cliente = ruc_valor if ruc_valor else None

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()

                # 1. Validar que no se duplique usuario o email en 'usuarios'
                cursor.execute('SELECT id FROM usuarios WHERE usuario = %s OR email = %s;', (nombre_usuario, email_usuario))
                if cursor.fetchone():
                    flash('El nombre de usuario o correo electrónico ya se encuentra registrado.', 'warning')
                    cursor.close()
                    return render_template('registro.html', form=form, sistema=SISTEMA_INFO)

                # 2. Si ingresó cédula/RUC, validar que no exista en 'clientes'
                if ruc_cliente:
                    cursor.execute('SELECT id FROM clientes WHERE ruc = %s;', (ruc_cliente,))
                    if cursor.fetchone():
                        flash('El número de cédula o RUC ingresado ya se encuentra registrado.', 'warning')
                        cursor.close()
                        return render_template('registro.html', form=form, sistema=SISTEMA_INFO)

                # 3. Insertar en tabla 'usuarios' con rol 'usuario'
                cursor.execute(
                    '''INSERT INTO usuarios (usuario, email, password, rol) 
                       VALUES (%s, %s, %s, %s) RETURNING id;''',
                    (nombre_usuario, email_usuario, hash_password, 'usuario')
                )
                res_id = cursor.fetchone()
                nuevo_id = res_id['id'] if isinstance(res_id, dict) else res_id[0]

                # 4. Insertar en tabla 'clientes' vinculando usuario_id
                cursor.execute(
                    '''INSERT INTO clientes (nombre, email, telefono, ruc, usuario_id)
                       VALUES (%s, %s, %s, %s, %s);''',
                    (nombre_usuario, email_usuario, 'Sin registrar', ruc_cliente, nuevo_id)
                )

                conn.commit()
                cursor.close()

                flash('Usuario registrado exitosamente. Por favor inicie sesión.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar la cuenta: {e}', 'danger')
            finally:
                conn.close()

    return render_template('registro.html', form=form, sistema=SISTEMA_INFO)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        captcha_ingresado = getattr(form, 'captcha', None)
        captcha_valor = captcha_ingresado.data.strip().upper() if captcha_ingresado else request.form.get('captcha', '').strip().upper()
        captcha_guardado = session.get('captcha_text', '')

        if not captcha_valor or captcha_valor != captcha_guardado:
            flash('Código de seguridad CAPTCHA incorrecto. Intente nuevamente.', 'danger')
            return render_template('login.html', form=form, sistema=SISTEMA_INFO)

        session.pop('captcha_text', None)

        identificador = form.usuario.data.strip()
        clave_candidata = form.password.data

        conn = obtener_conexion()
        if not conn:
            flash('No se pudo conectar con la base de datos.', 'danger')
            return render_template('login.html', form=form, sistema=SISTEMA_INFO)

        try:
            cursor = conn.cursor()
            
            # Busca si coincide con: usuario, email O el ruc/cédula del cliente asociado
            cursor.execute(
                '''SELECT u.id, u.usuario, u.password, u.rol, u.intentos_fallidos, u.bloqueado_hasta, u.email 
                   FROM usuarios u
                   LEFT JOIN clientes c ON c.usuario_id = u.id
                   WHERE u.usuario = %s OR LOWER(u.email) = LOWER(%s) OR c.ruc = %s
                   LIMIT 1;''', 
                (identificador, identificador, identificador)
            )
            usuario_db = cursor.fetchone()

            if usuario_db:
                ahora = datetime.now()
                bloqueado_hasta = usuario_db.get('bloqueado_hasta') if isinstance(usuario_db, dict) else usuario_db[5]

                # Comprobar bloqueo temporal
                if bloqueado_hasta and ahora < bloqueado_hasta:
                    minutos_restantes = int((bloqueado_hasta - ahora).total_seconds() / 60) + 1
                    flash(f'Cuenta bloqueada por seguridad tras 3 intentos fallidos. Intente nuevamente en {minutos_restantes} minuto(s).', 'danger')
                    cursor.close()
                    return render_template('login.html', form=form, sistema=SISTEMA_INFO)

                pass_hash = usuario_db['password'] if isinstance(usuario_db, dict) else usuario_db[2]
                id_usr = usuario_db['id'] if isinstance(usuario_db, dict) else usuario_db[0]
                rol_usr = (usuario_db.get('rol') if isinstance(usuario_db, dict) else usuario_db[3]) or 'usuario'
                usr_nom = usuario_db['usuario'] if isinstance(usuario_db, dict) else usuario_db[1]
                email_usr = usuario_db.get('email') if isinstance(usuario_db, dict) else usuario_db[6]
                intentos_prev = (usuario_db.get('intentos_fallidos') if isinstance(usuario_db, dict) else usuario_db[4]) or 0

                # Verificación de credenciales
                if check_password_hash(pass_hash, clave_candidata):
                    cursor.execute(
                        'UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s;',
                        (id_usr,)
                    )
                    conn.commit()
                    cursor.close()

                    usuario_obj = Usuario(
                        id=id_usr, 
                        usuario=usr_nom, 
                        password=pass_hash,
                        rol=rol_usr,
                        email=email_usr
                    )
                    login_user(usuario_obj)
                    flash(f'Bienvenido al sistema, {usuario_obj.usuario}.', 'success')
                    
                    next_page = request.args.get('next')
                    if next_page:
                        return redirect(next_page)
                    
                    # Redirección amigable por rol
                    if usuario_obj.rol == 'usuario':
                        return redirect(url_for('mis_facturas'))
                    return redirect(url_for('dashboard'))
                else:
                    intentos = intentos_prev + 1

                    if intentos >= 3:
                        tiempo_bloqueo = ahora + timedelta(minutes=15)
                        cursor.execute(
                            'UPDATE usuarios SET intentos_fallidos = %s, bloqueado_hasta = %s WHERE id = %s;',
                            (intentos, tiempo_bloqueo, id_usr)
                        )
                        conn.commit()
                        flash('Ha superado el límite de 3 intentos fallidos. Su cuenta ha sido bloqueada por 15 minutos.', 'danger')
                    else:
                        cursor.execute(
                            'UPDATE usuarios SET intentos_fallidos = %s WHERE id = %s;',
                            (intentos, id_usr)
                        )
                        conn.commit()
                        restantes = 3 - intentos
                        flash(f'Contraseña incorrecta. Le quedan {restantes} intento(s) antes del bloqueo.', 'warning')
                    
                    cursor.close()
            else:
                flash('Usuario o contraseña incorrectos.', 'danger')
                cursor.close()

        except Exception as e:
            conn.rollback()
            flash(f'Ocurrió un error al procesar la solicitud: {e}', 'danger')
        finally:
            conn.close()

    return render_template('login.html', form=form, sistema=SISTEMA_INFO)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión finalizada correctamente.', 'info')
    return redirect(url_for('login'))


# MÉTRICAS GLOBALES Y FINANCIERAS

def obtener_metricas_globales():
    conn = obtener_conexion()
    metricas = {
        'total_productos': 0,
        'total_clientes': 0,
        'total_proveedores': 0,
        'total_facturas': 0,
        'total_ingresos': 0.0,
        'total_pendiente': 0.0,
        'productos_bajo_stock': 0,
        'pendientes_recientes': []
    }
    
    if not conn:
        return metricas

    try:
        cursor = conn.cursor()

        # 1. Contadores generales de entidades
        cursor.execute("SELECT COUNT(*) FROM productos;")
        res = cursor.fetchone()
        metricas['total_productos'] = int(res[0] if not isinstance(res, dict) else res['count'])

        cursor.execute("SELECT COUNT(*) FROM clientes;")
        res = cursor.fetchone()
        metricas['total_clientes'] = int(res[0] if not isinstance(res, dict) else res['count'])

        cursor.execute("SELECT COUNT(*) FROM proveedores;")
        res = cursor.fetchone()
        metricas['total_proveedores'] = int(res[0] if not isinstance(res, dict) else res['count'])

        cursor.execute("SELECT COUNT(*) FROM facturas;")
        res = cursor.fetchone()
        metricas['total_facturas'] = int(res[0] if not isinstance(res, dict) else res['count'])

        # 2. Total recaudado efectivo/tarjeta (Facturas Pagadas, id_estado = 1)
        cursor.execute("SELECT COALESCE(SUM(monto), 0) FROM facturas WHERE id_estado = 1;")
        res = cursor.fetchone()
        metricas['total_ingresos'] = float(res[0] if not isinstance(res, dict) else res['coalesce'])

        # 3. Total por cobrar / conciliar (Facturas Pendientes, id_estado = 2)
        cursor.execute("SELECT COALESCE(SUM(monto), 0) FROM facturas WHERE id_estado = 2;")
        res = cursor.fetchone()
        metricas['total_pendiente'] = float(res[0] if not isinstance(res, dict) else res['coalesce'])

        # 4. Alerta de stock crítico (menor o igual a 5 unidades)
        cursor.execute("SELECT COUNT(*) FROM productos WHERE stock <= 5;")
        res = cursor.fetchone()
        metricas['productos_bajo_stock'] = int(res[0] if not isinstance(res, dict) else res['count'])

        # 5. Lista de comprobantes pendientes para cobro rápido (últimas 5)
        cursor.execute('''
            SELECT f.id, f.numero, f.fecha, f.monto,
                   COALESCE(c.nombre, 'Consumidor Final') AS cliente,
                   COALESCE(mp.nombre, 'Efectivo') AS metodo_pago
            FROM facturas f
            LEFT JOIN clientes c ON f.id_cliente = c.id
            LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
            WHERE f.id_estado = 2
            ORDER BY f.id DESC
            LIMIT 5;
        ''')
        filas = cursor.fetchall()
        cursor.close()

        for f in filas:
            metricas['pendientes_recientes'].append({
                'id': f['id'] if isinstance(f, dict) else f[0],
                'numero': f['numero'] if isinstance(f, dict) else f[1],
                'fecha': f['fecha'] if isinstance(f, dict) else f[2],
                'monto': float(f['monto'] if isinstance(f, dict) else f[3]),
                'cliente': f['cliente'] if isinstance(f, dict) else f[4],
                'metodo_pago': f['metodo_pago'] if isinstance(f, dict) else f[5]
            })

    except Exception as e:
        print(f"Error al obtener métricas globales: {e}")
    finally:
        conn.close()

    return metricas

# 1. PORTADA PÚBLICA (visible para cualquiera)
@app.route('/')
def inicio():
    metricas = obtener_metricas_globales()
    return render_template(
        'index.html',
        sistema=SISTEMA_INFO,
        mensaje="Plataforma de Control y Gestión",
        total_productos=metricas['total_productos'],
        total_clientes=metricas['total_clientes'],
        total_proveedores=metricas['total_proveedores'],
        total_facturas=metricas['total_facturas']
    )

# 2. PANEL PRIVADO (solo autenticados)
@app.route('/dashboard')
@login_required
def dashboard():
    # Seguridad: si el usuario autenticado es cliente, lo enviamos a sus compras
    if current_user.rol == 'usuario':
        return redirect(url_for('mis_facturas'))

    metricas = obtener_metricas_globales()

    return render_template(
        'dashboard.html',
        sistema=SISTEMA_INFO,
        m=metricas,
        total_productos=metricas['total_productos'],
        total_clientes=metricas['total_clientes'],
        total_proveedores=metricas['total_proveedores'],
        total_facturas=metricas['total_facturas'],
        total_ingresos=metricas['total_ingresos'],
        total_pendiente=metricas['total_pendiente'],
        productos_bajo_stock=metricas['productos_bajo_stock'],
        pendientes_recientes=metricas['pendientes_recientes']
    )

# MÓDULO 1: PRODUCTOS
# 1. LISTADO (SELECT con LEFT JOIN y fetchall)
@app.route('/productos')
@login_required
def productos():
    conn = obtener_conexion()
    productos_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.nombre, COALESCE(c.nombre, 'Sin categoría') AS categoria, p.precio, p.stock
                FROM productos p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                ORDER BY p.id DESC;
            ''')
            productos_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al obtener productos: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template('productos.html', productos=productos_db, sistema=SISTEMA_INFO)


# 2. AGREGAR (INSERT INTO parametrizado con commit)
@app.route('/productos/formulario', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def formulario_producto():
    form = ProductoForm()

    conn = obtener_conexion()
    if not conn:
        flash('Error al conectar con la base de datos.', 'danger')
        return redirect(url_for('productos'))

    categorias = []
    marcas = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
        categorias = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM marcas ORDER BY nombre ASC;')
        marcas = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f"Error al cargar opciones: {e}", "danger")
    finally:
        conn.close()

    # Inyectar opciones en los selects
    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices'):
        form.categoria.choices = [('', 'Seleccione una categoría')] + [(str(c['id']), c['nombre']) for c in categorias]
    
    if hasattr(form, 'marca') and hasattr(form.marca, 'choices'):
        form.marca.choices = [('', 'Sin marca / No aplica')] + [(str(m['id']), m['nombre']) for m in marcas]

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        precio = float(form.precio.data)
        stock = int(form.stock.data)
        id_categoria = int(form.categoria.data)

        # id_marca es nullable en la BD
        id_marca = None
        if hasattr(form, 'marca') and form.marca.data and str(form.marca.data).isdigit():
            id_marca = int(form.marca.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO productos (nombre, precio, stock, id_categoria, id_marca)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (nombre, precio, stock, id_categoria, id_marca))
                conn.commit()
                cursor.close()
                flash('Producto registrado correctamente.', 'success')
                return redirect(url_for('productos'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar el producto: {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Producto")


# 3. MODIFICAR (SELECT WHERE para cargar y UPDATE WHERE con commit)
@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def editar_producto(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('productos'))

    producto = None
    categorias = []
    marcas = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM productos WHERE id = %s;', (id,))
        producto = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
        categorias = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM marcas ORDER BY nombre ASC;')
        marcas = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f"Error al cargar producto: {e}", "danger")
    finally:
        conn.close()

    if not producto:
        flash('El producto solicitado no existe.', 'warning')
        return redirect(url_for('productos'))

    form = ProductoForm()
    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices'):
        form.categoria.choices = [('', 'Seleccione una categoría')] + [(str(c['id']), c['nombre']) for c in categorias]
    
    if hasattr(form, 'marca') and hasattr(form.marca, 'choices'):
        form.marca.choices = [('', 'Sin marca / No aplica')] + [(str(m['id']), m['nombre']) for m in marcas]

    if request.method == 'GET':
        form.nombre.data = producto['nombre']
        form.precio.data = producto['precio']
        form.stock.data = producto['stock']
        if hasattr(form, 'categoria'):
            form.categoria.data = str(producto['id_categoria'])
        if hasattr(form, 'marca') and producto.get('id_marca'):
            form.marca.data = str(producto['id_marca'])

    elif form.validate_on_submit():
        nombre = form.nombre.data.strip()
        precio = float(form.precio.data)
        stock = int(form.stock.data)
        id_categoria = int(form.categoria.data)

        id_marca = None
        if hasattr(form, 'marca') and form.marca.data and str(form.marca.data).isdigit():
            id_marca = int(form.marca.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE productos 
                    SET nombre = %s, precio = %s, stock = %s, id_categoria = %s, id_marca = %s
                    WHERE id = %s;
                ''', (nombre, precio, stock, id_categoria, id_marca, id))
                conn.commit()
                cursor.close()
                flash('Producto modificado exitosamente.', 'success')
                return redirect(url_for('productos'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al modificar el producto: {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_producto.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Producto")


# 4. ELIMINAR (DELETE WHERE con commit y manejo de integridad)
@app.route('/productos/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
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
            flash(f'No se puede eliminar el producto porque ya forma parte de facturas registradas.', 'danger')
        finally:
            conn.close()

    return redirect(url_for('productos'))

# MÓDULO: CLIENTES

# 1. LISTADO (SELECT con LEFT JOIN para nombre de ciudad)
@app.route('/clientes')
@login_required
@roles_requeridos('admin', 'operador')
def clientes():
    conn = obtener_conexion()
    clientes_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.id, c.nombre, c.ruc, c.telefono, c.email,
                       COALESCE(ci.nombre, 'No asignada') AS ciudad
                FROM clientes c
                LEFT JOIN ciudades ci ON c.id_ciudad = ci.id
                ORDER BY c.id DESC;
            ''')
            clientes_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al obtener clientes: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template('clientes.html', clientes=clientes_db, sistema=SISTEMA_INFO)


# 2. AGREGAR (INSERT INTO parametrizado con commit)
@app.route('/clientes/formulario', methods=['GET', 'POST'])
@roles_requeridos('admin', 'operador')
@login_required
def formulario_cliente():
    form = ClienteForm()

    conn = obtener_conexion()
    ciudades = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre FROM ciudades ORDER BY nombre ASC;')
            ciudades = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al cargar ciudades: {e}", "danger")
        finally:
            conn.close()

    # Cargar dropdown de ciudades de forma segura
    if hasattr(form, 'id_ciudad') and hasattr(form.id_ciudad, 'choices'):
        form.id_ciudad.choices = [('', 'Seleccione una ciudad (opcional)')] + [(str(c['id']), c['nombre']) for c in ciudades]

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        ruc = form.ruc.data.strip()
        telefono = form.telefono.data.strip()
        email = form.email.data.strip().lower()

        # Si no selecciona ciudad o no existe el campo, se envía None (NULL en PostgreSQL)
        id_ciudad = None
        if hasattr(form, 'id_ciudad') and form.id_ciudad.data and str(form.id_ciudad.data).isdigit():
            id_ciudad = int(form.id_ciudad.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO clientes (nombre, ruc, telefono, email, id_ciudad)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (nombre, ruc, telefono, email, id_ciudad))
                conn.commit()
                cursor.close()
                flash('Cliente registrado correctamente.', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar cliente (RUC duplicado o datos inválidos): {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Nuevo Cliente")


# 3. MODIFICAR (Precarga en GET y UPDATE en POST)
@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def editar_cliente(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('clientes'))

    cliente = None
    ciudades = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM clientes WHERE id = %s;', (id,))
        cliente = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM ciudades ORDER BY nombre ASC;')
        ciudades = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f"Error al consultar la base de datos: {e}", "danger")
    finally:
        conn.close()

    if not cliente:
        flash('El cliente solicitado no existe.', 'warning')
        return redirect(url_for('clientes'))

    form = ClienteForm()
    if hasattr(form, 'id_ciudad') and hasattr(form.id_ciudad, 'choices'):
        form.id_ciudad.choices = [('', 'Seleccione una ciudad (opcional)')] + [(str(c['id']), c['nombre']) for c in ciudades]

    # En GET poblamos el formulario con los datos de PostgreSQL
    if request.method == 'GET':
        form.nombre.data = cliente['nombre']
        form.ruc.data = cliente['ruc']
        form.telefono.data = cliente['telefono']
        form.email.data = cliente['email']
        if hasattr(form, 'id_ciudad') and cliente.get('id_ciudad'):
            form.id_ciudad.data = str(cliente['id_ciudad'])

    # En POST validamos y actualizamos
    elif form.validate_on_submit():
        nombre = form.nombre.data.strip()
        ruc = form.ruc.data.strip()
        telefono = form.telefono.data.strip()
        email = form.email.data.strip().lower()

        id_ciudad = None
        if hasattr(form, 'id_ciudad') and form.id_ciudad.data and str(form.id_ciudad.data).isdigit():
            id_ciudad = int(form.id_ciudad.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE clientes
                    SET nombre = %s, ruc = %s, telefono = %s, email = %s, id_ciudad = %s
                    WHERE id = %s;
                ''', (nombre, ruc, telefono, email, id_ciudad, id))
                conn.commit()
                cursor.close()
                flash('Cliente actualizado correctamente.', 'success')
                return redirect(url_for('clientes'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al modificar: El RUC ya pertenece a otro cliente o hubo un fallo en el servidor. Detalle: {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_cliente.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Cliente")


# 4. ELIMINAR (DELETE con validación preventiva de facturas y commit)
@app.route('/clientes/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_cliente(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            # Validación preventiva de clave foránea en la tabla facturas
            cursor.execute('SELECT COUNT(*) FROM facturas WHERE id_cliente = %s;', (id,))
            res = cursor.fetchone()
            facturas_asociadas = res['count'] if isinstance(res, dict) else res[0]

            if facturas_asociadas > 0:
                flash('No se puede eliminar el cliente porque tiene facturas emitidas registradas en el sistema.', 'warning')
            else:
                cursor.execute('DELETE FROM clientes WHERE id = %s;', (id,))
                conn.commit()
                flash('Cliente eliminado satisfactoriamente.', 'info')
            cursor.close()
        except Exception as e:
            conn.rollback()
            flash(f'Error al eliminar cliente: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('clientes'))

# MÓDULO 3: PROVEEDORES

# 1. LISTADO (SELECT con LEFT JOIN y fetchall)
@app.route('/proveedores')
@login_required
@roles_requeridos('admin', 'operador')
def proveedores():
    conn = obtener_conexion()
    proveedores_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.nombre, p.contacto, p.telefono, 
                       COALESCE(c.nombre, 'Sin categoría') AS categoria,
                       COALESCE(ci.nombre, 'No asignada') AS ciudad
                FROM proveedores p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                LEFT JOIN ciudades ci ON p.id_ciudad = ci.id
                ORDER BY p.id DESC;
            ''')
            proveedores_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al obtener proveedores: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template('proveedores.html', proveedores=proveedores_db, sistema=SISTEMA_INFO)


# 2. AGREGAR (INSERT INTO parametrizado con commit)
@app.route('/proveedores/formulario', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def formulario_proveedor():
    form = ProveedorForm()

    conn = obtener_conexion()
    if not conn:
        flash('Error al conectar con la base de datos.', 'danger')
        return redirect(url_for('proveedores'))

    categorias = []
    ciudades = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
        categorias = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM ciudades ORDER BY nombre ASC;')
        ciudades = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f"Error al cargar opciones: {e}", "danger")
    finally:
        conn.close()

    # Cargar dropdowns
    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices'):
        form.categoria.choices = [('', 'Seleccione una categoría')] + [(str(c['id']), c['nombre']) for c in categorias]

    if hasattr(form, 'id_ciudad') and hasattr(form.id_ciudad, 'choices'):
        form.id_ciudad.choices = [('', 'Seleccione una ciudad (opcional)')] + [(str(ci['id']), ci['nombre']) for ci in ciudades]

    if form.validate_on_submit():
        nombre = form.nombre.data.strip()
        contacto = form.contacto.data.strip()
        telefono = form.telefono.data.strip()
        id_categoria = int(form.categoria.data)

        id_ciudad = None
        if hasattr(form, 'id_ciudad') and form.id_ciudad.data and str(form.id_ciudad.data).isdigit():
            id_ciudad = int(form.id_ciudad.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO proveedores (nombre, contacto, telefono, id_categoria, id_ciudad)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (nombre, contacto, telefono, id_categoria, id_ciudad))
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


# 3. MODIFICAR (Precarga en GET y UPDATE en POST con commit)
@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def editar_proveedor(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('proveedores'))

    proveedor = None
    categorias = []
    ciudades = []
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM proveedores WHERE id = %s;', (id,))
        proveedor = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre ASC;')
        categorias = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM ciudades ORDER BY nombre ASC;')
        ciudades = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f"Error al cargar información del proveedor: {e}", "danger")
    finally:
        conn.close()

    if not proveedor:
        flash('El proveedor solicitado no existe.', 'warning')
        return redirect(url_for('proveedores'))

    form = ProveedorForm()
    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices'):
        form.categoria.choices = [('', 'Seleccione una categoría')] + [(str(c['id']), c['nombre']) for c in categorias]

    if hasattr(form, 'id_ciudad') and hasattr(form.id_ciudad, 'choices'):
        form.id_ciudad.choices = [('', 'Seleccione una ciudad (opcional)')] + [(str(ci['id']), ci['nombre']) for ci in ciudades]

    if request.method == 'GET':
        form.nombre.data = proveedor['nombre']
        form.contacto.data = proveedor['contacto']
        form.telefono.data = proveedor['telefono']
        if hasattr(form, 'categoria'):
            form.categoria.data = str(proveedor['id_categoria'])
        if hasattr(form, 'id_ciudad') and proveedor.get('id_ciudad'):
            form.id_ciudad.data = str(proveedor['id_ciudad'])

    elif form.validate_on_submit():
        nombre = form.nombre.data.strip()
        contacto = form.contacto.data.strip()
        telefono = form.telefono.data.strip()
        id_categoria = int(form.categoria.data)

        id_ciudad = None
        if hasattr(form, 'id_ciudad') and form.id_ciudad.data and str(form.id_ciudad.data).isdigit():
            id_ciudad = int(form.id_ciudad.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE proveedores 
                    SET nombre = %s, contacto = %s, telefono = %s, id_categoria = %s, id_ciudad = %s
                    WHERE id = %s;
                ''', (nombre, contacto, telefono, id_categoria, id_ciudad, id))
                conn.commit()
                cursor.close()
                flash('Proveedor actualizado exitosamente.', 'success')
                return redirect(url_for('proveedores'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al actualizar proveedor: {e}', 'danger')
            finally:
                conn.close()

    return render_template('formulario_proveedor.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Proveedor")


# 4. ELIMINAR (DELETE WHERE restringido a POST con commit)
@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
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
            flash(f'No se puede eliminar el proveedor (posible referencia de compras o productos asociados): {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('proveedores'))
# ==============================================================================
# MÓDULO 4: FACTURACIÓN & CARRITO DE COMPRAS
# ==============================================================================

# 1. LISTADO ADMINISTRATIVO (SELECT con JOINs)
@app.route('/facturacion')
@login_required
@roles_requeridos('admin', 'operador')
def facturacion():
    conn = obtener_conexion()
    facturas_db = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.numero, c.nombre AS cliente, f.fecha, f.monto, 
                       e.nombre AS estado, COALESCE(mp.nombre, 'Efectivo') AS metodo_pago
                FROM facturas f
                INNER JOIN clientes c ON f.id_cliente = c.id
                INNER JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                ORDER BY f.id DESC;
            ''')
            facturas_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al listar facturas: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template('facturacion.html', facturas=facturas_db, sistema=SISTEMA_INFO)

# 2. AGREGAR FACTURA MANUALMENTE (ADMIN / OPERADOR)
@app.route('/facturacion/formulario', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def formulario_facturacion():
    conn = obtener_conexion()
    if not conn:
        flash('Error al conectar con la base de datos.', 'danger')
        return redirect(url_for('facturacion'))

    clientes_bd = []
    estados_bd = []
    productos_bd = []
    metodos_bd = []

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nombre FROM clientes ORDER BY nombre ASC;')
        clientes_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM estados_factura ORDER BY id ASC;')
        estados_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM metodos_pago ORDER BY id ASC;')
        metodos_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE stock > 0 ORDER BY nombre ASC;')
        filas_productos = cursor.fetchall()
        productos_bd = [
            {
                'id': p['id'] if isinstance(p, dict) else p[0],
                'nombre': str(p['nombre'] if isinstance(p, dict) else p[1]),
                'precio': float(p['precio'] if isinstance(p, dict) else p[2]),
                'stock': int(p['stock'] if isinstance(p, dict) else p[3])
            }
            for p in filas_productos
        ]
        cursor.close()
    except Exception as e:
        flash(f"Error al cargar datos del formulario: {e}", "danger")
    finally:
        conn.close()

    form = FacturacionForm()
    if hasattr(form, 'cliente') and hasattr(form.cliente, 'choices'):
        form.cliente.choices = [('', 'Seleccione un cliente')] + [
            (str(c['id'] if isinstance(c, dict) else c[0]), c['nombre'] if isinstance(c, dict) else c[1]) 
            for c in clientes_bd
        ]

    if form.validate_on_submit():
        numero = form.numero.data.strip().upper()
        fecha = str(form.fecha.data)

        cliente_input = str(form.cliente.data).strip()
        id_cliente = int(cliente_input) if cliente_input.isdigit() else 1
        if not cliente_input.isdigit():
            for c in clientes_bd:
                c_nom = c['nombre'] if isinstance(c, dict) else c[1]
                c_id = c['id'] if isinstance(c, dict) else c[0]
                if c_nom == cliente_input:
                    id_cliente = c_id
                    break

        estado_input = getattr(form, 'estado', None)
        id_estado = 1
        if estado_input and estado_input.data:
            val_estado = str(estado_input.data).strip().capitalize()
            for e in estados_bd:
                e_nom = e['nombre'] if isinstance(e, dict) else e[1]
                e_id = e['id'] if isinstance(e, dict) else e[0]
                if e_nom == val_estado or str(e_id) == val_estado:
                    id_estado = e_id
                    break

        # Capturar método de pago seleccionado desde el formulario manual
        metodo_input = request.form.get('id_metodo_pago', '1')
        try:
            id_metodo_pago = int(metodo_input)
        except (ValueError, TypeError):
            id_metodo_pago = 1

        prod_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio[]')

        if not prod_ids:
            flash('Debe seleccionar al menos un producto para generar la factura.', 'warning')
            return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura", productos_lista=productos_bd, metodos_lista=metodos_bd)

        items_validos = []
        total_acumulado = 0.0

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                for p_id, cant_str, prec_str in zip(prod_ids, cantidades, precios):
                    if not p_id:
                        continue
                    cant = int(cant_str)
                    prec = float(prec_str)

                    cursor.execute('SELECT nombre, stock FROM productos WHERE id = %s;', (int(p_id),))
                    prod_info = cursor.fetchone()

                    stock_real = (prod_info['stock'] if isinstance(prod_info, dict) else prod_info[1]) if prod_info else 0
                    nom_prod = (prod_info['nombre'] if isinstance(prod_info, dict) else prod_info[0]) if prod_info else ''

                    if not prod_info or cant > stock_real:
                        flash(f"Stock insuficiente para '{nom_prod}'. Disponible: {stock_real}, solicitado: {cant}.", 'danger')
                        cursor.close()
                        return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura", productos_lista=productos_bd, metodos_lista=metodos_bd)

                    subtotal = round(cant * prec, 2)
                    total_acumulado += subtotal
                    items_validos.append({
                        'id_producto': int(p_id),
                        'cantidad': cant,
                        'precio': prec,
                        'subtotal': subtotal
                    })

                cursor.execute('''
                    INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id;
                ''', (numero, fecha, total_acumulado, id_cliente, id_estado, id_metodo_pago))

                nueva_fac = cursor.fetchone()
                id_factura = nueva_fac['id'] if isinstance(nueva_fac, dict) else nueva_fac[0]

                for item in items_validos:
                    cursor.execute('UPDATE productos SET stock = stock - %s WHERE id = %s;', (item['cantidad'], item['id_producto']))
                    cursor.execute('''
                        INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario, subtotal)
                        VALUES (%s, %s, %s, %s, %s);
                    ''', (id_factura, item['id_producto'], item['cantidad'], item['precio'], item['subtotal']))

                conn.commit()
                cursor.close()
                flash('Factura registrada y stock actualizado con éxito.', 'success')
                return redirect(url_for('facturacion'))

            except Exception as e:
                conn.rollback()
                error_msg = str(e)
                if 'facturas_numero_key' in error_msg or 'llave duplicada' in error_msg or 'unique constraint' in error_msg.lower():
                    flash(f'El número de factura "{numero}" ya se encuentra registrado. Por favor, asigna el número siguiente.', 'warning')
                else:
                    flash(f'Error al procesar la factura: {e}', 'danger')
                return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Nueva Factura", productos_lista=productos_bd, metodos_lista=metodos_bd)
            finally:
                conn.close()

    return render_template(
        'formulario_facturacion.html', 
        form=form, 
        sistema=SISTEMA_INFO, 
        titulo="Nueva Factura", 
        productos_lista=productos_bd,
        metodos_lista=metodos_bd,
        detalles_guardados=[]
    )


# 3. MODIFICAR FACTURA (ADMIN / OPERADOR)
@app.route('/facturacion/editar/<numero>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def editar_factura(numero):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('facturacion'))

    factura = None
    clientes_bd = []
    estados_bd = []
    productos_bd = []
    detalles_bd = []

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM facturas WHERE numero = %s;', (numero,))
        factura = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM clientes ORDER BY nombre ASC;')
        clientes_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM estados_factura ORDER BY id ASC;')
        estados_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre, precio, stock FROM productos ORDER BY nombre ASC;')
        productos_bd = [
            {
                'id': p['id'] if isinstance(p, dict) else p[0],
                'nombre': str(p['nombre'] if isinstance(p, dict) else p[1]),
                'precio': float(p['precio'] if isinstance(p, dict) else p[2]),
                'stock': int(p['stock'] if isinstance(p, dict) else p[3])
            }
            for p in cursor.fetchall()
        ]

        if factura:
            fac_id = factura['id'] if isinstance(factura, dict) else factura[0]
            cursor.execute('''
                SELECT d.id_producto, p.nombre, d.precio_unitario, d.cantidad, d.subtotal, p.stock
                FROM detalle_facturas d
                INNER JOIN productos p ON d.id_producto = p.id
                WHERE d.id_factura = %s;
            ''', (fac_id,))
            detalles_bd = [
                {
                    'id_producto': d['id_producto'] if isinstance(d, dict) else d[0],
                    'cantidad': int(d['cantidad'] if isinstance(d, dict) else d[3]),
                    'precio': float(d['precio_unitario'] if isinstance(d, dict) else d[2]),
                    'stock': int(d['stock'] if isinstance(d, dict) else d[5]) + int(d['cantidad'] if isinstance(d, dict) else d[3])
                }
                for d in cursor.fetchall()
            ]

        cursor.close()
    except Exception as e:
        flash(f"Error al cargar factura para edición: {e}", "danger")
    finally:
        conn.close()

    if not factura:
        flash('Factura no encontrada.', 'warning')
        return redirect(url_for('facturacion'))

    form = FacturacionForm()
    if hasattr(form, 'cliente') and hasattr(form.cliente, 'choices'):
        form.cliente.choices = [('', 'Seleccione un cliente')] + [
            (str(c['id'] if isinstance(c, dict) else c[0]), c['nombre'] if isinstance(c, dict) else c[1]) 
            for c in clientes_bd
        ]

    fac_id = factura['id'] if isinstance(factura, dict) else factura[0]
    fac_num = factura['numero'] if isinstance(factura, dict) else factura[1]
    fac_fecha = factura['fecha'] if isinstance(factura, dict) else factura[2]
    fac_monto = factura['monto'] if isinstance(factura, dict) else factura[3]
    fac_id_cliente = factura['id_cliente'] if isinstance(factura, dict) else factura[4]
    fac_id_estado = factura['id_estado'] if isinstance(factura, dict) else factura[5]

    if request.method == 'GET':
        form.numero.data = fac_num
        form.fecha.data = fac_fecha
        form.monto.data = fac_monto
        if hasattr(form, 'cliente'):
            form.cliente.data = str(fac_id_cliente)
        if hasattr(form, 'estado'):
            for e in estados_bd:
                e_id = e['id'] if isinstance(e, dict) else e[0]
                e_nom = e['nombre'] if isinstance(e, dict) else e[1]
                if e_id == fac_id_estado:
                    form.estado.data = str(e_id) if form.estado.choices and form.estado.choices[0][0].isdigit() else e_nom
                    break

    elif form.validate_on_submit():
        nuevo_numero = form.numero.data.strip().upper()
        fecha = str(form.fecha.data)

        cliente_input = str(form.cliente.data).strip()
        id_cliente = int(cliente_input) if cliente_input.isdigit() else fac_id_cliente
        if not cliente_input.isdigit():
            for c in clientes_bd:
                c_nom = c['nombre'] if isinstance(c, dict) else c[1]
                c_id = c['id'] if isinstance(c, dict) else c[0]
                if c_nom == cliente_input:
                    id_cliente = c_id
                    break

        estado_input = getattr(form, 'estado', None)
        id_estado = fac_id_estado
        if estado_input and estado_input.data:
            val_estado = str(estado_input.data).strip().capitalize()
            for e in estados_bd:
                e_nom = e['nombre'] if isinstance(e, dict) else e[1]
                e_id = e['id'] if isinstance(e, dict) else e[0]
                if e_nom == val_estado or str(e_id) == val_estado:
                    id_estado = e_id
                    break

        prod_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio[]')

        items_validos = []
        total_acumulado = 0.0

        for p_id, cant_str, prec_str in zip(prod_ids, cantidades, precios):
            if p_id and cant_str:
                cant = int(cant_str)
                prec = float(prec_str)
                subt = round(cant * prec, 2)
                total_acumulado += subt
                items_validos.append({
                    'id_producto': int(p_id),
                    'cantidad': cant,
                    'precio': prec,
                    'subtotal': subt
                })

        monto_final = total_acumulado if items_validos else float(form.monto.data or 0.0)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()

                # Revertir stock previo
                cursor.execute('SELECT id_producto, cantidad FROM detalle_facturas WHERE id_factura = %s;', (fac_id,))
                previos = cursor.fetchall()
                for prev in previos:
                    prev_cant = prev['cantidad'] if isinstance(prev, dict) else prev[1]
                    prev_pid = prev['id_producto'] if isinstance(prev, dict) else prev[0]
                    cursor.execute('UPDATE productos SET stock = stock + %s WHERE id = %s;', (prev_cant, prev_pid))

                cursor.execute('DELETE FROM detalle_facturas WHERE id_factura = %s;', (fac_id,))

                # Descontar nuevo inventario
                for item in items_validos:
                    cursor.execute('SELECT nombre, stock FROM productos WHERE id = %s;', (item['id_producto'],))
                    prod_info = cursor.fetchone()
                    stock_disp = (prod_info['stock'] if isinstance(prod_info, dict) else prod_info[1]) if prod_info else 0
                    nom_prod = (prod_info['nombre'] if isinstance(prod_info, dict) else prod_info[0]) if prod_info else ''

                    if not prod_info or item['cantidad'] > stock_disp:
                        conn.rollback()
                        flash(f"Stock insuficiente para '{nom_prod}'. Disponible: {stock_disp}, solicitado: {item['cantidad']}.", 'danger')
                        cursor.close()
                        return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Factura", productos_lista=productos_bd, detalles_guardados=detalles_bd)

                    cursor.execute('UPDATE productos SET stock = stock - %s WHERE id = %s;', (item['cantidad'], item['id_producto']))
                    cursor.execute('''
                        INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario, subtotal)
                        VALUES (%s, %s, %s, %s, %s);
                    ''', (fac_id, item['id_producto'], item['cantidad'], item['precio'], item['subtotal']))

                cursor.execute('''
                    UPDATE facturas
                    SET numero = %s, fecha = %s, monto = %s, id_cliente = %s, id_estado = %s
                    WHERE id = %s;
                ''', (nuevo_numero, fecha, monto_final, id_cliente, id_estado, fac_id))

                conn.commit()
                cursor.close()
                flash('Factura actualizada y stock ajustado correctamente.', 'success')
                return redirect(url_for('facturacion'))

            except Exception as e:
                conn.rollback()
                error_msg = str(e)
                if 'facturas_numero_key' in error_msg or 'llave duplicada' in error_msg or 'unique constraint' in error_msg.lower():
                    flash(f'El número de factura "{nuevo_numero}" ya está registrado en otra factura.', 'warning')
                else:
                    flash(f'Error al modificar la factura: {e}', 'danger')
                return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Factura", productos_lista=productos_bd, detalles_guardados=detalles_bd)
            finally:
                conn.close()

    return render_template('formulario_facturacion.html', form=form, sistema=SISTEMA_INFO, titulo="Editar Factura", productos_lista=productos_bd, detalles_guardados=detalles_bd)


# 4. ELIMINAR FACTURA (ADMIN)
@app.route('/facturacion/eliminar/<numero>', methods=['POST'])
@login_required
@roles_requeridos('admin')
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


# 5. HISTORIAL DE COMPRAS DEL CLIENTE
@app.route('/mis-facturas')
@login_required
def mis_facturas():
    conn = obtener_conexion()
    facturas_usuario = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado, 
                       COALESCE(e.nombre, 'Pagada') AS estado,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago
                FROM facturas f
                INNER JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                WHERE c.usuario_id = %s
                ORDER BY f.fecha DESC, f.id DESC;
            ''', (int(current_user.id),))
            filas = cursor.fetchall()
            cursor.close()

            for fila in filas:
                facturas_usuario.append({
                    'id': fila['id'] if isinstance(fila, dict) else fila[0],
                    'numero': fila['numero'] if isinstance(fila, dict) else fila[1],
                    'fecha': fila['fecha'] if isinstance(fila, dict) else fila[2],
                    'monto': float(fila['monto'] if isinstance(fila, dict) else fila[3]),
                    'id_estado': fila['id_estado'] if isinstance(fila, dict) else fila[4],
                    'estado': fila['estado'] if isinstance(fila, dict) else fila[5],
                    'metodo_pago': fila['metodo_pago'] if isinstance(fila, dict) else fila[6]
                })

        except Exception as e:
            flash(f"Error al obtener tus compras: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión con la base de datos.", "danger")

    return render_template('mis_facturas.html', facturas=facturas_usuario, sistema=SISTEMA_INFO)


# 6. VER COMPROBANTE / IMPRIMIR FACTURA
@app.route('/facturacion/descargar/<int:id_factura>')
@login_required
def descargar_factura(id_factura):
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('dashboard'))

    try:
        cursor = conn.cursor()

        # Si es cliente estándar, solo puede ver sus facturas vinculadas por usuario_id
        if current_user.rol == 'usuario':
            cursor.execute('''
                SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado, 
                       COALESCE(e.nombre, 'Pagada') AS estado,
                       COALESCE(c.nombre, 'Consumidor Final') AS cliente, 
                       c.email, c.ruc, c.telefono,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago
                FROM facturas f
                LEFT JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                WHERE f.id = %s AND c.usuario_id = %s;
            ''', (id_factura, int(current_user.id)))
        else:
            cursor.execute('''
                SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado, 
                       COALESCE(e.nombre, 'Pagada') AS estado,
                       COALESCE(c.nombre, 'Consumidor Final') AS cliente, 
                       c.email, c.ruc, c.telefono,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago
                FROM facturas f
                LEFT JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                WHERE f.id = %s;
            ''', (id_factura,))

        fila_fac = cursor.fetchone()

        if not fila_fac:
            flash("Comprobante no encontrado o acceso denegado.", "danger")
            cursor.close()
            return redirect(url_for('mis_facturas' if current_user.rol == 'usuario' else 'facturacion'))

        factura_dict = {
            'id': fila_fac['id'] if isinstance(fila_fac, dict) else fila_fac[0],
            'numero': fila_fac['numero'] if isinstance(fila_fac, dict) else fila_fac[1],
            'fecha': fila_fac['fecha'] if isinstance(fila_fac, dict) else fila_fac[2],
            'monto': float(fila_fac['monto'] if isinstance(fila_fac, dict) else fila_fac[3]),
            'estado': fila_fac['estado'] if isinstance(fila_fac, dict) else fila_fac[5],
            'cliente': fila_fac['cliente'] if isinstance(fila_fac, dict) else fila_fac[6],
            'email': fila_fac['email'] if isinstance(fila_fac, dict) else fila_fac[7],
            'ruc': fila_fac['ruc'] if isinstance(fila_fac, dict) else fila_fac[8],
            'telefono': fila_fac['telefono'] if isinstance(fila_fac, dict) else fila_fac[9],
            'metodo_pago': fila_fac['metodo_pago'] if isinstance(fila_fac, dict) else fila_fac[10]
        }

        cursor.execute('''
            SELECT COALESCE(p.nombre, 'Producto General') AS nombre, 
                   df.cantidad, 
                   df.precio_unitario, 
                   df.subtotal
            FROM detalle_facturas df
            LEFT JOIN productos p ON df.id_producto = p.id
            WHERE df.id_factura = %s;
        ''', (factura_dict['id'],))
        
        filas_detalles = cursor.fetchall()
        cursor.close()

        detalles_lista = [
            {
                'nombre': d['nombre'] if isinstance(d, dict) else d[0],
                'cantidad': int(d['cantidad'] if isinstance(d, dict) else d[1]),
                'precio': float(d['precio_unitario'] if isinstance(d, dict) else d[2]),
                'subtotal': float(d['subtotal'] if isinstance(d, dict) else d[3])
            }
            for d in filas_detalles
        ]

        return render_template(
            'factura_imprimible.html',
            factura=factura_dict,
            detalles=detalles_lista,
            sistema=SISTEMA_INFO
        )
    except Exception as e:
        flash(f"Error al generar comprobante: {e}", "danger")
        return redirect(url_for('dashboard'))
    finally:
        conn.close()


# 6.1 CAMBIAR ESTADO DE FACTURA (ADMIN Y OPERADOR)
@app.route('/facturacion/cambiar-estado/<int:id_factura>', methods=['POST'])
@login_required
def cambiar_estado_factura(id_factura):
    if current_user.rol not in ['admin', 'operador']:
        flash('No tiene permisos para modificar el estado de las facturas.', 'danger')
        return redirect(url_for('dashboard'))

    nuevo_estado = request.form.get('id_estado')
    try:
        nuevo_estado_id = int(nuevo_estado)
    except (ValueError, TypeError):
        flash('Estado de factura inválido.', 'warning')
        return redirect(url_for('facturacion'))

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('facturacion'))

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT numero, id_estado FROM facturas WHERE id = %s;', (id_factura,))
        factura = cursor.fetchone()
        if not factura:
            flash('Factura no encontrada.', 'warning')
            cursor.close()
            return redirect(url_for('facturacion'))

        num_factura = factura['numero'] if isinstance(factura, dict) else factura[0]

        cursor.execute('''
            UPDATE facturas 
            SET id_estado = %s 
            WHERE id = %s;
        ''', (nuevo_estado_id, id_factura))

        conn.commit()
        cursor.close()

        if nuevo_estado_id == 1:
            flash(f'¡Pago confirmado! La factura {num_factura} fue marcada como PAGADA.', 'success')
        elif nuevo_estado_id == 3:
            flash(f'La factura {num_factura} ha sido ANULADA.', 'info')
        else:
            flash(f'Estado de la factura {num_factura} actualizado con éxito.', 'primary')

    except Exception as e:
        conn.rollback()
        flash(f'Error al cambiar el estado de la factura: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('facturacion'))


# 7. GESTIÓN DEL CARRITO EN SESIÓN Y FACTURACIÓN MÚLTIPLE

# 7.1 AGREGAR PRODUCTO AL CARRITO
@app.route('/carrito/agregar/<int:id_producto>', methods=['POST'])
@login_required
def agregar_al_carrito(id_producto):
    try:
        cantidad = int(request.form.get('cantidad', 1))
        if cantidad < 1:
            cantidad = 1
    except ValueError:
        cantidad = 1

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('productos'))

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE id = %s;', (id_producto,))
        prod = cursor.fetchone()
        cursor.close()

        if not prod:
            flash('Producto no encontrado.', 'warning')
            return redirect(url_for('productos'))

        nombre_prod = prod['nombre'] if isinstance(prod, dict) else prod[1]
        precio_prod = float(prod['precio'] if isinstance(prod, dict) else prod[2])
        stock_prod = int(prod['stock'] if isinstance(prod, dict) else prod[3])

        if 'carrito' not in session:
            session['carrito'] = {}

        carrito = session['carrito']
        prod_id_str = str(id_producto)
        cant_actual = carrito.get(prod_id_str, {}).get('cantidad', 0)
        nueva_cant = cant_actual + cantidad

        if nueva_cant > stock_prod:
            flash(f'No puedes agregar {nueva_cant} unidades. Solo hay {stock_prod} en inventario.', 'warning')
            return redirect(url_for('productos'))

        carrito[prod_id_str] = {
            'id': id_producto,
            'nombre': nombre_prod,
            'precio': precio_prod,
            'cantidad': nueva_cant,
            'subtotal': round(precio_prod * nueva_cant, 2)
        }

        session['carrito'] = carrito
        session.modified = True
        flash(f'Se agregaron {cantidad} unidad(es) de "{nombre_prod}" al carrito.', 'success')
        return redirect(url_for('ver_carrito'))

    except Exception as e:
        flash(f'Error al agregar al carrito: {e}', 'danger')
        return redirect(url_for('productos'))
    finally:
        conn.close()


# 7.2 ACTUALIZAR CANTIDAD (+, -, o número manual)
@app.route('/carrito/actualizar/<int:id_producto>', methods=['POST'])
@login_required
def actualizar_carrito(id_producto):
    carrito = session.get('carrito', {})
    prod_id_str = str(id_producto)

    if prod_id_str not in carrito:
        flash('El producto no está en el carrito.', 'warning')
        return redirect(url_for('ver_carrito'))

    accion = request.form.get('accion')
    cant_actual = carrito[prod_id_str]['cantidad']

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('ver_carrito'))

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT stock FROM productos WHERE id = %s;', (id_producto,))
        prod = cursor.fetchone()
        cursor.close()

        stock_disponible = int(prod['stock'] if isinstance(prod, dict) else prod[0]) if prod else 0

        if accion == 'sumar':
            nueva_cant = cant_actual + 1
        elif accion == 'restar':
            nueva_cant = cant_actual - 1
        else:
            try:
                nueva_cant = int(request.form.get('cantidad', cant_actual))
            except ValueError:
                nueva_cant = cant_actual

        if nueva_cant <= 0:
            del carrito[prod_id_str]
            session['carrito'] = carrito
            session.modified = True
            flash('Producto removido del carrito.', 'info')
            return redirect(url_for('ver_carrito'))

        if nueva_cant > stock_disponible:
            flash(f'No hay suficiente stock. Máximo disponible: {stock_disponible} unidades.', 'warning')
            return redirect(url_for('ver_carrito'))

        carrito[prod_id_str]['cantidad'] = nueva_cant
        carrito[prod_id_str]['subtotal'] = round(carrito[prod_id_str]['precio'] * nueva_cant, 2)
        session['carrito'] = carrito
        session.modified = True

    except Exception as e:
        flash(f'Error al actualizar el carrito: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('ver_carrito'))


# 7.3 VER EL CARRITO CON MÉTODOS DE PAGO
@app.route('/carrito')
@login_required
def ver_carrito():
    carrito = session.get('carrito', {})
    items = list(carrito.values())
    total = sum(item['subtotal'] for item in items)
    
    conn = obtener_conexion()
    metodos_pago = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre FROM metodos_pago ORDER BY id ASC;')
            metodos_pago = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al cargar métodos de pago: {e}", "warning")
        finally:
            conn.close()

    return render_template(
        'carrito.html', 
        items=items, 
        total=total, 
        metodos_pago=metodos_pago, 
        sistema=SISTEMA_INFO
    )


# 7.4 ELIMINAR UN PRODUCTO DEL CARRITO
@app.route('/carrito/eliminar/<int:id_producto>', methods=['POST'])
@login_required
def eliminar_del_carrito(id_producto):
    carrito = session.get('carrito', {})
    prod_id_str = str(id_producto)
    if prod_id_str in carrito:
        del carrito[prod_id_str]
        session['carrito'] = carrito
        session.modified = True
        flash('Producto removido del carrito.', 'info')
    return redirect(url_for('ver_carrito'))


# 7.5 VACIAR TODO EL CARRITO
@app.route('/carrito/vaciar', methods=['POST'])
@login_required
def vaciar_carrito():
    session.pop('carrito', None)
    flash('Se ha vaciado el carrito de compras.', 'info')
    return redirect(url_for('ver_carrito'))


# 7.6 FINALIZAR COMPRA Y CREAR FACTURA MÚLTIPLE
@app.route('/carrito/finalizar-compra', methods=['POST'])
@login_required
def finalizar_compra():
    carrito = session.get('carrito', {})
    if not carrito:
        flash('El carrito está vacío. Agrega productos antes de confirmar.', 'warning')
        return redirect(url_for('productos'))

    # Recibir método de pago enviado desde el selector o tarjetas de pago
    metodo_pago_val = request.form.get('metodo_pago', '1')
    try:
        id_metodo_pago = int(metodo_pago_val)
    except ValueError:
        id_metodo_pago = 1

    # Definir estado contable: Tarjeta (3) = Pagada (1); Efectivo (1) o Transferencia (2) = Pendiente (2)
    id_estado_factura = 1 if id_metodo_pago == 3 else 2

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('ver_carrito'))

    try:
        cursor = conn.cursor()

        # 1. Obtener cliente_id asociado al usuario en sesión
        cursor.execute('SELECT id FROM clientes WHERE usuario_id = %s LIMIT 1;', (int(current_user.id),))
        cliente = cursor.fetchone()
        if not cliente:
            flash('No se encontró su perfil de cliente asociado.', 'danger')
            cursor.close()
            return redirect(url_for('productos'))

        id_cliente = cliente['id'] if isinstance(cliente, dict) else cliente[0]

        # 2. Validar stock de cada producto en el carrito
        monto_total = 0.0
        items_a_procesar = []

        for prod_id_str, item in carrito.items():
            id_prod = int(prod_id_str)
            cant_solicitada = int(item['cantidad'])

            cursor.execute('SELECT nombre, precio, stock FROM productos WHERE id = %s FOR UPDATE;', (id_prod,))
            prod_db = cursor.fetchone()

            if not prod_db:
                flash(f'El producto "{item["nombre"]}" ya no está disponible.', 'danger')
                conn.rollback()
                cursor.close()
                return redirect(url_for('ver_carrito'))

            stock_disponible = int(prod_db['stock'] if isinstance(prod_db, dict) else prod_db[2])
            precio_real = float(prod_db['precio'] if isinstance(prod_db, dict) else prod_db[1])
            nombre_real = prod_db['nombre'] if isinstance(prod_db, dict) else prod_db[0]

            if cant_solicitada > stock_disponible:
                flash(f'Stock insuficiente para "{nombre_real}". Disponible: {stock_disponible}.', 'warning')
                conn.rollback()
                cursor.close()
                return redirect(url_for('ver_carrito'))

            subtotal_item = round(precio_real * cant_solicitada, 2)
            monto_total += subtotal_item
            items_a_procesar.append((id_prod, cant_solicitada, precio_real, subtotal_item))

        # 3. Generar número de factura secuencial limpio y correlativo (FAC-YYYY-XXX)
        anio_actual = datetime.now().year
        prefijo = f"FAC-{anio_actual}-"

        cursor.execute('''
            SELECT COALESCE(
                MAX(CAST(SUBSTRING(numero FROM '^FAC-[0-9]{4}-([0-9]{3,4})$') AS INTEGER)), 
                0
            ) + 1 AS siguiente_secuencia
            FROM facturas 
            WHERE numero ~ %s;
        ''', (f'^FAC-{anio_actual}-[0-9]{{3,4}}$',))

        res_secuencia = cursor.fetchone()
        if isinstance(res_secuencia, dict):
            siguiente_id = int(res_secuencia.get('siguiente_secuencia', 1))
        else:
            siguiente_id = int(res_secuencia[0])

        numero_factura = f"{prefijo}{siguiente_id:03d}"

        cursor.execute('''
            INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago)
            VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)
            RETURNING id;
        ''', (numero_factura, monto_total, id_cliente, id_estado_factura, id_metodo_pago))

        res_fac = cursor.fetchone()
        id_factura = res_fac['id'] if isinstance(res_fac, dict) else res_fac[0]

        # 4. Insertar filas en detalle_facturas y descontar stock
        for id_prod, cant, precio, subtotal in items_a_procesar:
            cursor.execute('''
                INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (%s, %s, %s, %s, %s);
            ''', (id_factura, id_prod, cant, precio, subtotal))

            cursor.execute('UPDATE productos SET stock = stock - %s WHERE id = %s;', (cant, id_prod))

        conn.commit()
        cursor.close()

        # 5. Vaciar carrito de la sesión y redirigir
        session.pop('carrito', None)

        flash(f'¡Compra confirmada con éxito! Factura {numero_factura} generada.', 'success')
        return redirect(url_for('mis_facturas'))

    except Exception as e:
        conn.rollback()
        flash(f'Error al procesar la compra múltiple: {e}', 'danger')
        return redirect(url_for('ver_carrito'))
    finally:
        conn.close()

# INICIO DE LA APLICACIÓN
if __name__ == '__main__':
    app.run(debug=True)