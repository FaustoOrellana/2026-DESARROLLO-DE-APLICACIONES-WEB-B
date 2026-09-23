import os
import io
import random
import math
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

from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'techmanager_dev_fallback_key_2026')

csrf = CSRFProtect(app)

# --- CONFIGURACIÓN FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Debe iniciar sesión para acceder a esta sección.'
login_manager.login_message_category = 'warning'


def extraer_columna(fila, clave, indice, default=None):
    """Extrae valores de forma agnóstica soportando RealDictCursor y tuplas."""
    if fila is None:
        return default
    if isinstance(fila, dict):
        return fila.get(clave, default)
    try:
        return fila[indice]
    except (IndexError, TypeError):
        return default


@login_manager.user_loader
def load_user(user_id):
    # 1. Validación estricta del identificador
    if not user_id or not str(user_id).isdigit():
        return None

    conn = obtener_conexion()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.usuario, u.password, u.rol, u.email, u.activo, c.nombre
            FROM usuarios u
            LEFT JOIN clientes c ON c.usuario_id = u.id
            WHERE u.id = %s
            LIMIT 1;
        ''', (int(user_id),))
        u = cursor.fetchone()
        cursor.close()

        if u:
            id_db = extraer_columna(u, 'id', 0)
            usuario_db = extraer_columna(u, 'usuario', 1)
            pass_db = extraer_columna(u, 'password', 2)
            rol_db = extraer_columna(u, 'rol', 3, 'usuario')
            email_db = extraer_columna(u, 'email', 4)
            activo_db = extraer_columna(u, 'activo', 5, True)
            nombre_db = extraer_columna(u, 'nombre', 6)

            # Si el usuario está inactivo (Soft-Delete), invalidar sesión
            if activo_db is False:
                return None

            return Usuario(
                id=id_db,
                usuario=usuario_db,
                password=pass_db,
                rol=rol_db or 'usuario',
                email=email_db,
                activo=True,
                nombre=nombre_db or usuario_db
            )
    except Exception as e:
        print(f"❌ Error al cargar usuario en load_user: {e}")
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
                
                # Evita bucles de redirección según el rol
                if getattr(current_user, 'rol', 'usuario') == 'usuario':
                    return redirect(url_for('mis_facturas'))
                
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

# MÓDULO DE AUTENTICACIÓN Y REGISTRO (CON NOMBRES Y APELLIDOS)
# --- RUTA DE REGISTRO ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated:
        if current_user.tiene_rol('admin', 'operador'):
            return redirect(url_for('dashboard'))
        return redirect(url_for('mis_facturas'))

    form = UsuarioForm()
    if form.validate_on_submit():
        captcha_ingresado = getattr(form, 'captcha', None)
        captcha_valor = captcha_ingresado.data.strip().upper() if captcha_ingresado else request.form.get('captcha', '').strip().upper()
        captcha_guardado = session.get('captcha_text', '')

        if not captcha_valor or captcha_valor != captcha_guardado:
            flash('Código de seguridad CAPTCHA incorrecto. Intente nuevamente.', 'danger')
            return render_template('registro.html', form=form, sistema=SISTEMA_INFO)

        session.pop('captcha_text', None)

        # Captura y formateo de datos personales
        nombres = form.nombres.data.strip().title()
        apellidos = form.apellidos.data.strip().title()
        nombre_completo = f"{nombres} {apellidos}"

        nombre_usuario = form.usuario.data.strip().lower()
        email_usuario = form.email.data.strip().lower()
        hash_password = generate_password_hash(form.password.data)

        # Captura de RUC/Cédula y teléfono
        ruc_campo = getattr(form, 'ruc', None)
        ruc_valor = ruc_campo.data.strip() if ruc_campo and ruc_campo.data else request.form.get('ruc', '').strip()
        ruc_cliente = ruc_valor if ruc_valor else None

        tel_campo = getattr(form, 'telefono', None)
        telefono_cliente = tel_campo.data.strip() if tel_campo and tel_campo.data else request.form.get('telefono', '').strip()

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

                # 2. Validar que no exista la cédula/RUC en 'clientes'
                if ruc_cliente:
                    cursor.execute('SELECT id FROM clientes WHERE ruc = %s;', (ruc_cliente,))
                    if cursor.fetchone():
                        flash('El número de cédula o RUC ingresado ya se encuentra registrado.', 'warning')
                        cursor.close()
                        return render_template('registro.html', form=form, sistema=SISTEMA_INFO)

                # 3. Insertar en tabla 'usuarios' con rol estándar 'usuario'
                cursor.execute(
                    '''INSERT INTO usuarios (usuario, email, password, rol, activo) 
                       VALUES (%s, %s, %s, %s, TRUE) RETURNING id;''',
                    (nombre_usuario, email_usuario, hash_password, 'usuario')
                )
                res_id = cursor.fetchone()
                nuevo_id = res_id['id'] if isinstance(res_id, dict) else res_id[0]

                # 4. Insertar en tabla 'clientes' con el nombre completo y auditoría
                cursor.execute(
                    '''INSERT INTO clientes (nombre, email, telefono, ruc, usuario_id, activo, created_by)
                       VALUES (%s, %s, %s, %s, %s, TRUE, %s);''',
                    (nombre_completo, email_usuario, telefono_cliente, ruc_cliente, nuevo_id, nombre_usuario)
                )

                conn.commit()
                cursor.close()

                flash('Cuenta creada exitosamente. Inicie sesión con sus credenciales.', 'success')
                return redirect(url_for('login'))

            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar la cuenta: {e}', 'danger')
            finally:
                conn.close()

    return render_template('registro.html', form=form, sistema=SISTEMA_INFO)


# --- RUTA DE LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.tiene_rol('admin', 'operador'):
            return redirect(url_for('dashboard'))
        return redirect(url_for('mis_facturas'))

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
            
            cursor.execute(
                '''SELECT u.id, u.usuario, u.password, u.rol, u.intentos_fallidos, u.bloqueado_hasta, u.email 
                   FROM usuarios u
                   LEFT JOIN clientes c ON c.usuario_id = u.id
                   WHERE (u.usuario = %s OR LOWER(u.email) = LOWER(%s) OR c.ruc = %s)
                     AND u.activo = TRUE
                   LIMIT 1;''', 
                (identificador, identificador, identificador)
            )
            usuario_db = cursor.fetchone()

            if usuario_db:
                ahora = datetime.now()
                rol_usr = (usuario_db.get('rol') if isinstance(usuario_db, dict) else usuario_db[3]) or 'usuario'
                bloqueado_hasta = usuario_db.get('bloqueado_hasta') if isinstance(usuario_db, dict) else usuario_db[5]

                # 1. Comprobar bloqueo temporal (SOLO si NO es admin)
                if rol_usr != 'admin' and bloqueado_hasta and ahora < bloqueado_hasta:
                    minutos_restantes = int((bloqueado_hasta - ahora).total_seconds() / 60) + 1
                    flash(f'Cuenta bloqueada temporalmente por seguridad. Intente nuevamente en {minutos_restantes} minuto(s).', 'danger')
                    cursor.close()
                    return render_template('login.html', form=form, sistema=SISTEMA_INFO)

                pass_hash = usuario_db['password'] if isinstance(usuario_db, dict) else usuario_db[2]
                id_usr = usuario_db['id'] if isinstance(usuario_db, dict) else usuario_db[0]
                usr_nom = usuario_db['usuario'] if isinstance(usuario_db, dict) else usuario_db[1]
                email_usr = usuario_db.get('email') if isinstance(usuario_db, dict) else usuario_db[6]
                intentos_prev = (usuario_db.get('intentos_fallidos') if isinstance(usuario_db, dict) else usuario_db[4]) or 0

                # 2. Verificación de credenciales
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
                    
                    if usuario_obj.rol == 'usuario':
                        return redirect(url_for('mis_facturas'))
                    return redirect(url_for('dashboard'))
                else:
                    # 3. Contraseña incorrecta
                    if rol_usr == 'admin':
                        flash('Contraseña de administrador incorrecta.', 'danger')
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


# --- RUTA DE LOGOUT ---
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión finalizada correctamente.', 'info')
    return redirect(url_for('login'))

# MÉTRICAS GLOBALES Y FINANCIERAS (AUDITADAS Y SOLO ACTIVAS)
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
        'facturas_recientes': [],
        'pendientes_recientes': []  # Mantenido por retrocompatibilidad
    }
    
    if not conn:
        return metricas

    try:
        cursor = conn.cursor()

        # 1. Contadores generales de entidades activas
        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = TRUE;")
        res = cursor.fetchone()
        metricas['total_productos'] = int(res[0] if not isinstance(res, (dict, object)) or hasattr(res, 'keys') and not res else (res['count'] if isinstance(res, dict) else res[0]))

        cursor.execute("SELECT COUNT(*) FROM clientes WHERE activo = TRUE;")
        res = cursor.fetchone()
        metricas['total_clientes'] = int(res[0] if not isinstance(res, dict) else res.get('count', 0))

        cursor.execute("SELECT COUNT(*) FROM proveedores WHERE activo = TRUE;")
        res = cursor.fetchone()
        metricas['total_proveedores'] = int(res[0] if not isinstance(res, dict) else res.get('count', 0))

        cursor.execute("SELECT COUNT(*) FROM facturas WHERE activo = TRUE;")
        res = cursor.fetchone()
        metricas['total_facturas'] = int(res[0] if not isinstance(res, dict) else res.get('count', 0))

        # 2. Total recaudado real (Facturas Pagadas y Activas, id_estado = 1)
        cursor.execute("SELECT COALESCE(SUM(monto), 0) FROM facturas WHERE activo = TRUE AND id_estado = 1;")
        res = cursor.fetchone()
        val_ingresos = res[0] if not isinstance(res, dict) else (res.get('coalesce') or res.get('sum') or 0)
        metricas['total_ingresos'] = float(val_ingresos)

        # Total pendiente
        metricas['total_pendiente'] = 0.0

        # 3. Alerta de stock crítico en catálogo activo (stock <= 5 unidades)
        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = TRUE AND stock <= 5;")
        res = cursor.fetchone()
        metricas['productos_bajo_stock'] = int(res[0] if not isinstance(res, dict) else res.get('count', 0))

        # 4. Últimas 5 facturas emitidas ordenadas por ID de manera segura
        cursor.execute('''
            SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado,
                   COALESCE(c.nombre, 'Consumidor Final') AS cliente,
                   COALESCE(mp.nombre, 'Efectivo') AS metodo_pago,
                   COALESCE(e.nombre, 'Pagada') AS estado
            FROM facturas f
            LEFT JOIN clientes c ON f.id_cliente = c.id
            LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
            LEFT JOIN estados_factura e ON f.id_estado = e.id
            WHERE f.activo = TRUE
            ORDER BY f.id DESC
            LIMIT 5;
        ''')
        filas = cursor.fetchall()
        cursor.close()

        lista_ventas = []
        for f in filas:
            # Extracción segura compatible con tuplas posicionales y diccionarios
            if isinstance(f, dict):
                item = {
                    'id': f.get('id'),
                    'numero': f.get('numero'),
                    'fecha': f.get('fecha'),
                    'monto': float(f.get('monto') or 0.0),
                    'id_estado': int(f.get('id_estado') or 1),
                    'cliente': f.get('cliente', 'Consumidor Final'),
                    'metodo_pago': f.get('metodo_pago', 'Efectivo'),
                    'estado': f.get('estado', 'Pagada')
                }
            else:
                item = {
                    'id': f[0],
                    'numero': f[1],
                    'fecha': f[2],
                    'monto': float(f[3] or 0.0),
                    'id_estado': int(f[4] if len(f) > 4 and f[4] is not None else 1),
                    'cliente': f[5] if len(f) > 5 else 'Consumidor Final',
                    'metodo_pago': f[6] if len(f) > 6 else 'Efectivo',
                    'estado': f[7] if len(f) > 7 else 'Pagada'
                }
            lista_ventas.append(item)

        metricas['facturas_recientes'] = lista_ventas
        metricas['pendientes_recientes'] = lista_ventas  # Por compatibilidad

    except Exception as e:
        print(f"Error al obtener métricas globales: {e}")
    finally:
        conn.close()

    return metricas


# CONTROLADORES DE ENTRADA Y PANEL
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


# 2. PANEL PRIVADO (solo autenticados: admin y operador)
@app.route('/dashboard')
@login_required
def dashboard():
    # Seguridad: usuarios finales van a su panel de compras
    if current_user.rol == 'usuario':
        return redirect(url_for('mis_facturas'))

    metricas = obtener_metricas_globales()

    # Extracción y conversión segura de métricas escalares para evitar excepciones en Jinja2
    def convertir_valor(val, tipo=int, defecto=0):
        try:
            if val is None:
                return defecto
            if isinstance(val, (list, tuple)):
                val = val[0]
            if isinstance(val, dict):
                val = list(val.values())[0] if val else defecto
            return tipo(val)
        except Exception:
            return defecto

    tot_prod = convertir_valor(metricas.get('total_productos', 0), int, 0)
    tot_cli = convertir_valor(metricas.get('total_clientes', 0), int, 0)
    tot_prov = convertir_valor(metricas.get('total_proveedores', 0), int, 0)
    tot_fac = convertir_valor(metricas.get('total_facturas', 0), int, 0)
    tot_ing = convertir_valor(metricas.get('total_ingresos', 0.0), float, 0.0)
    tot_pend = convertir_valor(metricas.get('total_pendiente', 0.0), float, 0.0)
    prod_stock = convertir_valor(metricas.get('productos_bajo_stock', 0), int, 0)

    # Normalización estricta de facturas recientes a diccionarios puros
    facturas_limpias = []
    raw_facturas = metricas.get('facturas_recientes', [])
    if isinstance(raw_facturas, (list, tuple)):
        for f in raw_facturas:
            if isinstance(f, dict):
                facturas_limpias.append({
                    'id': convertir_valor(f.get('id'), int, 0),
                    'numero': str(f.get('numero', 'N/A')),
                    'fecha': str(f.get('fecha', '')),
                    'monto': convertir_valor(f.get('monto'), float, 0.0),
                    'id_estado': convertir_valor(f.get('id_estado'), int, 1),
                    'cliente': str(f.get('cliente', 'Consumidor Final')),
                    'metodo_pago': str(f.get('metodo_pago', 'Efectivo')),
                    'estado': str(f.get('estado', 'Pagada'))
                })
            elif isinstance(f, (list, tuple)):
                facturas_limpias.append({
                    'id': convertir_valor(f[0] if len(f) > 0 else 0, int, 0),
                    'numero': str(f[1] if len(f) > 1 else 'N/A'),
                    'fecha': str(f[2] if len(f) > 2 else ''),
                    'monto': convertir_valor(f[3] if len(f) > 3 else 0.0, float, 0.0),
                    'id_estado': convertir_valor(f[4] if len(f) > 4 else 1, int, 1),
                    'cliente': str(f[5] if len(f) > 5 else 'Consumidor Final'),
                    'metodo_pago': str(f[6] if len(f) > 6 else 'Efectivo'),
                    'estado': str(f[7] if len(f) > 7 else 'Pagada')
                })

    return render_template(
        'dashboard.html',
        sistema=SISTEMA_INFO,
        m=metricas,
        total_productos=tot_prod,
        total_clientes=tot_cli,
        total_proveedores=tot_prov,
        total_facturas=tot_fac,
        total_ingresos=tot_ing,
        total_pendiente=tot_pend,
        productos_bajo_stock=prod_stock,
        facturas_recientes=facturas_limpias,
        pendientes_recientes=facturas_limpias
    )

# MÓDULO 1: PRODUCTOS
# 1. LISTADO (SELECT con LEFT JOIN, búsqueda, paginación y filtro de activos)
@app.route('/productos')
@login_required
def productos():
    conn = obtener_conexion()
    productos_db = []
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    total_pages = 1

    if conn:
        try:
            cursor = conn.cursor()
            
            # Construcción dinámica de filtros
            where_sql = "WHERE p.activo = TRUE"
            params = []
            
            if q:
                where_sql += """ AND (
                    p.nombre ILIKE %s OR 
                    COALESCE(c.nombre, '') ILIKE %s OR 
                    COALESCE(p.descripcion, '') ILIKE %s
                )"""
                param_busqueda = f"%{q}%"
                params.extend([param_busqueda, param_busqueda, param_busqueda])

            # Conteo total para paginación (soporta tuplas y diccionarios)
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM productos p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            if row_count:
                total_items = row_count['total'] if isinstance(row_count, dict) else row_count[0]
            else:
                total_items = 0
            
            total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

            # Consulta paginada con LIMIT y OFFSET
            query_datos = f'''
                SELECT p.id, p.nombre, p.descripcion, COALESCE(c.nombre, 'Sin categoría') AS categoria, p.precio, p.stock
                FROM productos p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                {where_sql}
                ORDER BY p.id DESC
                LIMIT %s OFFSET %s;
            '''
            params_datos = list(params) + [per_page, offset]
            cursor.execute(query_datos, tuple(params_datos))
            productos_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al obtener productos: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template(
        'productos.html', 
        productos=productos_db, 
        sistema=SISTEMA_INFO,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        q=q
    )


# 2. AGREGAR (INSERT INTO con descripcion, created_by y commit)
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
        descripcion = form.descripcion.data.strip() if hasattr(form, 'descripcion') and form.descripcion.data else None

        id_marca = None
        if hasattr(form, 'marca') and form.marca.data and str(form.marca.data).isdigit():
            id_marca = int(form.marca.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO productos (nombre, precio, stock, id_categoria, id_marca, descripcion, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                ''', (nombre, precio, stock, id_categoria, id_marca, descripcion, current_user.usuario))
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


# 3. MODIFICAR (UPDATE WHERE con descripcion, modified_by y commit)
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
        cursor.execute('SELECT * FROM productos WHERE id = %s AND activo = TRUE;', (id,))
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
        flash('El producto solicitado no existe o ha sido dado de baja.', 'warning')
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
        if hasattr(form, 'descripcion'):
            form.descripcion.data = producto.get('descripcion') or ''
        if hasattr(form, 'categoria'):
            form.categoria.data = str(producto['id_categoria'])
        if hasattr(form, 'marca') and producto.get('id_marca'):
            form.marca.data = str(producto['id_marca'])

    elif form.validate_on_submit():
        nombre = form.nombre.data.strip()
        precio = float(form.precio.data)
        stock = int(form.stock.data)
        id_categoria = int(form.categoria.data)
        descripcion = form.descripcion.data.strip() if hasattr(form, 'descripcion') and form.descripcion.data else None

        id_marca = None
        if hasattr(form, 'marca') and form.marca.data and str(form.marca.data).isdigit():
            id_marca = int(form.marca.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE productos 
                    SET nombre = %s, precio = %s, stock = %s, id_categoria = %s, id_marca = %s, descripcion = %s, modified_by = %s
                    WHERE id = %s;
                ''', (nombre, precio, stock, id_categoria, id_marca, descripcion, current_user.usuario, id))
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


# 4. ELIMINAR / DAR DE BAJA (CONTROL ESTRICTO: STOCK E INTEGRIDAD REFERENCIAL)
@app.route('/productos/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_producto(id):
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('productos'))

    try:
        cursor = conn.cursor()

        # 1. Obtener datos actuales del producto
        cursor.execute("SELECT id, nombre, stock, activo FROM productos WHERE id = %s;", (id,))
        prod = cursor.fetchone()

        if not prod:
            flash("El producto no existe o ya ha sido removido.", "warning")
            cursor.close()
            return redirect(url_for('productos'))

        prod_id = extraer_columna(prod, 'id', 0)
        prod_nombre = extraer_columna(prod, 'nombre', 1)
        prod_stock = int(extraer_columna(prod, 'stock', 2, 0))
        prod_activo = extraer_columna(prod, 'activo', 3, True)

        if not prod_activo:
            flash(f"El producto '{prod_nombre}' ya se encuentra dado de baja.", "info")
            cursor.close()
            return redirect(url_for('productos'))

        # REGLA 1: BLOQUEO POR EXISTENCIA DE STOCK
        if prod_stock > 0:
            flash(
                f"Acción denegada: El producto '{prod_nombre}' registra {prod_stock} unidad(es) en bodega. "
                f"Por normativa contable, no puede desactivar un artículo con existencias físicas disponibles.",
                "warning"
            )
            cursor.close()
            return redirect(url_for('productos'))

        # REGLA 2: BLOQUEO POR FACTURAS PENDIENTES DE PAGO / LIQUIDACIÓN
        cursor.execute('''
            SELECT COUNT(DISTINCT f.id) AS total_pendientes
            FROM detalle_facturas df
            INNER JOIN facturas f ON df.id_factura = f.id
            WHERE df.id_producto = %s AND f.activo = TRUE AND f.id_estado = 2;
        ''', (prod_id,))
        row_pendientes = cursor.fetchone()
        facturas_pendientes = int(extraer_columna(row_pendientes, 'total_pendientes', 0, 0))

        if facturas_pendientes > 0:
            flash(
                f"Acción denegada: El producto '{prod_nombre}' forma parte de {facturas_pendientes} factura(s) "
                f"pendientes de pago. Resuelva o anule dichos comprobantes antes de retirar el producto.",
                "danger"
            )
            cursor.close()
            return redirect(url_for('productos'))

        # 3. Soft Delete seguro (solo cuando stock = 0 y no compromete operaciones pendientes)
        cursor.execute('''
            UPDATE productos 
            SET activo = FALSE, modified_by = %s 
            WHERE id = %s;
        ''', (current_user.usuario, prod_id))

        conn.commit()
        cursor.close()
        flash(f"Producto '{prod_nombre}' dado de baja satisfactoriamente del catálogo activo.", "info")

    except Exception as e:
        conn.rollback()
        flash(f"Error al procesar la baja del producto: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('productos'))

# MÓDULO: CLIENTES

# 1. LISTADO (SELECT con LEFT JOIN, búsqueda, paginación y filtro de activos)
@app.route('/clientes')
@login_required
@roles_requeridos('admin', 'operador')
def clientes():
    conn = obtener_conexion()
    clientes_db = []
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    total_pages = 1

    if conn:
        try:
            cursor = conn.cursor()
            
            # Filtro base: solo clientes activos
            where_sql = "WHERE c.activo = TRUE"
            params = []
            
            if q:
                where_sql += """ AND (
                    c.nombre ILIKE %s OR 
                    c.ruc ILIKE %s OR 
                    COALESCE(c.email, '') ILIKE %s OR 
                    COALESCE(ci.nombre, '') ILIKE %s
                )"""
                param_busqueda = f"%{q}%"
                params.extend([param_busqueda, param_busqueda, param_busqueda, param_busqueda])

            # Conteo total para paginación (soporta tuplas y diccionarios de forma segura)
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM clientes c
                LEFT JOIN ciudades ci ON c.id_ciudad = ci.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            if row_count:
                total_items = row_count['total'] if isinstance(row_count, dict) else row_count[0]
            else:
                total_items = 0
            
            total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

            # Consulta paginada con LIMIT y OFFSET
            query_datos = f'''
                SELECT c.id, c.nombre, c.ruc, c.telefono, c.email,
                       COALESCE(ci.nombre, 'No asignada') AS ciudad
                FROM clientes c
                LEFT JOIN ciudades ci ON c.id_ciudad = ci.id
                {where_sql}
                ORDER BY c.id DESC
                LIMIT %s OFFSET %s;
            '''
            params_datos = list(params) + [per_page, offset]
            cursor.execute(query_datos, tuple(params_datos))
            clientes_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al obtener clientes: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template(
        'clientes.html', 
        clientes=clientes_db, 
        sistema=SISTEMA_INFO,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        q=q
    )


# 2. AGREGAR (INSERT INTO parametrizado con created_by y commit)
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

        id_ciudad = None
        if hasattr(form, 'id_ciudad') and form.id_ciudad.data and str(form.id_ciudad.data).isdigit():
            id_ciudad = int(form.id_ciudad.data)

        conn = obtener_conexion()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO clientes (nombre, ruc, telefono, email, id_ciudad, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s);
                ''', (nombre, ruc, telefono, email, id_ciudad, current_user.usuario))
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


# 3. MODIFICAR (Precarga de activos en GET y UPDATE con modified_by en POST)
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
        cursor.execute('SELECT * FROM clientes WHERE id = %s AND activo = TRUE;', (id,))
        cliente = cursor.fetchone()

        cursor.execute('SELECT id, nombre FROM ciudades ORDER BY nombre ASC;')
        ciudades = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash(f"Error al consultar la base de datos: {e}", "danger")
    finally:
        conn.close()

    if not cliente:
        flash('El cliente solicitado no existe o ha sido dado de baja.', 'warning')
        return redirect(url_for('clientes'))

    form = ClienteForm()
    if hasattr(form, 'id_ciudad') and hasattr(form.id_ciudad, 'choices'):
        form.id_ciudad.choices = [('', 'Seleccione una ciudad (opcional)')] + [(str(c['id']), c['nombre']) for c in ciudades]

    if request.method == 'GET':
        form.nombre.data = cliente['nombre']
        form.ruc.data = cliente['ruc']
        form.telefono.data = cliente['telefono']
        form.email.data = cliente['email']
        if hasattr(form, 'id_ciudad') and cliente.get('id_ciudad'):
            form.id_ciudad.data = str(cliente['id_ciudad'])

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
                    SET nombre = %s, ruc = %s, telefono = %s, email = %s, id_ciudad = %s, modified_by = %s
                    WHERE id = %s;
                ''', (nombre, ruc, telefono, email, id_ciudad, current_user.usuario, id))
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


# 4. ELIMINAR (SOFT DELETE: UPDATE activo = FALSE con modified_by y commit)
@app.route('/clientes/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_cliente(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            # En lugar de DELETE físico, se realiza borrado lógico preservando la integridad referencial con facturas.
            # El trigger global registra automáticamente el evento 'SOFT_DELETE' en auditoria.
            cursor.execute('''
                UPDATE clientes 
                SET activo = FALSE, modified_by = %s 
                WHERE id = %s;
            ''', (current_user.usuario, id))
            conn.commit()
            cursor.close()
            flash('Cliente dado de baja satisfactoriamente.', 'info')
        except Exception as e:
            conn.rollback()
            flash(f'Error al dar de baja al cliente: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('clientes'))

# MÓDULO 3: PROVEEDORES

# 1. LISTADO (SELECT con LEFT JOIN, búsqueda, paginación y filtro de activos)
@app.route('/proveedores')
@login_required
@roles_requeridos('admin', 'operador')
def proveedores():
    conn = obtener_conexion()
    proveedores_db = []
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    total_pages = 1

    if conn:
        try:
            cursor = conn.cursor()
            
            # Filtro base: solo proveedores activos
            where_sql = "WHERE p.activo = TRUE"
            params = []

            if q:
                where_sql += """ AND (
                    p.nombre ILIKE %s OR 
                    COALESCE(p.contacto, '') ILIKE %s OR 
                    COALESCE(p.telefono, '') ILIKE %s OR 
                    COALESCE(c.nombre, '') ILIKE %s OR 
                    COALESCE(ci.nombre, '') ILIKE %s
                )"""
                param_busqueda = f"%{q}%"
                params.extend([param_busqueda, param_busqueda, param_busqueda, param_busqueda, param_busqueda])

            # Conteo total para paginación (soporta tuplas y diccionarios)
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM proveedores p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                LEFT JOIN ciudades ci ON p.id_ciudad = ci.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            if row_count:
                total_items = row_count['total'] if isinstance(row_count, dict) else row_count[0]
            else:
                total_items = 0

            total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

            # Consulta paginada con LIMIT y OFFSET
            query_datos = f'''
                SELECT p.id, p.nombre, p.contacto, p.telefono, 
                       COALESCE(c.nombre, 'Sin categoría') AS categoria,
                       COALESCE(ci.nombre, 'No asignada') AS ciudad
                FROM proveedores p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                LEFT JOIN ciudades ci ON p.id_ciudad = ci.id
                {where_sql}
                ORDER BY p.id DESC
                LIMIT %s OFFSET %s;
            '''
            params_datos = list(params) + [per_page, offset]
            cursor.execute(query_datos, tuple(params_datos))
            proveedores_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al obtener proveedores: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template(
        'proveedores.html', 
        proveedores=proveedores_db, 
        sistema=SISTEMA_INFO,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        q=q
    )


# 2. AGREGAR (INSERT INTO con created_by y commit)
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
        contacto = form.contacto.data.strip() if hasattr(form, 'contacto') and form.contacto.data else None
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
                    INSERT INTO proveedores (nombre, contacto, telefono, id_categoria, id_ciudad, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s);
                ''', (nombre, contacto, telefono, id_categoria, id_ciudad, current_user.usuario))
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


# 3. MODIFICAR (Precarga de activos en GET y UPDATE con modified_by en POST)
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
        cursor.execute('SELECT * FROM proveedores WHERE id = %s AND activo = TRUE;', (id,))
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
        flash('El proveedor solicitado no existe o ha sido dado de baja.', 'warning')
        return redirect(url_for('proveedores'))

    form = ProveedorForm()
    if hasattr(form, 'categoria') and hasattr(form.categoria, 'choices'):
        form.categoria.choices = [('', 'Seleccione una categoría')] + [(str(c['id']), c['nombre']) for c in categorias]

    if hasattr(form, 'id_ciudad') and hasattr(form.id_ciudad, 'choices'):
        form.id_ciudad.choices = [('', 'Seleccione una ciudad (opcional)')] + [(str(ci['id']), ci['nombre']) for ci in ciudades]

    if request.method == 'GET':
        form.nombre.data = proveedor['nombre']
        if hasattr(form, 'contacto'):
            form.contacto.data = proveedor.get('contacto') or ''
        form.telefono.data = proveedor['telefono']
        if hasattr(form, 'categoria'):
            form.categoria.data = str(proveedor['id_categoria'])
        if hasattr(form, 'id_ciudad') and proveedor.get('id_ciudad'):
            form.id_ciudad.data = str(proveedor['id_ciudad'])

    elif form.validate_on_submit():
        nombre = form.nombre.data.strip()
        contacto = form.contacto.data.strip() if hasattr(form, 'contacto') and form.contacto.data else None
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
                    SET nombre = %s, contacto = %s, telefono = %s, id_categoria = %s, id_ciudad = %s, modified_by = %s
                    WHERE id = %s;
                ''', (nombre, contacto, telefono, id_categoria, id_ciudad, current_user.usuario, id))
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


# 4. ELIMINAR (SOFT DELETE: UPDATE activo = FALSE con modified_by y commit)
@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_proveedor(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            # Borrado lógico: preserva la integridad referencial y registra la auditoría automáticamente
            cursor.execute('''
                UPDATE proveedores 
                SET activo = FALSE, modified_by = %s 
                WHERE id = %s;
            ''', (current_user.usuario, id))
            conn.commit()
            cursor.close()
            flash('Proveedor dado de baja satisfactoriamente.', 'info')
        except Exception as e:
            conn.rollback()
            flash(f'Error al dar de baja el proveedor: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('proveedores'))
# ==============================================================================
# MÓDULO 4: FACTURACIÓN & CARRITO DE COMPRAS
# ==============================================================================

# 1. LISTADO ADMINISTRATIVO (Búsqueda, Paginación, Detalle de Productos y Filtro de Activas)
@app.route('/facturacion')
@login_required
@roles_requeridos('admin', 'operador')
def facturacion():
    conn = obtener_conexion()
    facturas_db = []
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()
    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    total_pages = 1

    if conn:
        try:
            cursor = conn.cursor()
            
            where_sql = "WHERE f.activo = TRUE"
            params = []

            # Permite buscar por N° comprobante, Cliente, RUC o Nombre de Producto facturado
            if q:
                where_sql += """ AND (
                    f.numero ILIKE %s OR 
                    c.nombre ILIKE %s OR 
                    COALESCE(c.ruc, '') ILIKE %s OR
                    EXISTS (
                        SELECT 1 FROM detalle_facturas df_s
                        INNER JOIN productos p_s ON df_s.id_producto = p_s.id
                        WHERE df_s.id_factura = f.id AND p_s.nombre ILIKE %s
                    )
                )"""
                param_busqueda = f"%{q}%"
                params.extend([param_busqueda, param_busqueda, param_busqueda, param_busqueda])

            # Conteo total para paginación
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM facturas f
                INNER JOIN clientes c ON f.id_cliente = c.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            total_items = extraer_columna(row_count, 'total', 0, 0)
            total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

            # Consulta paginada con consolidación atómica de productos
            query_datos = f'''
                SELECT f.id, 
                       f.numero, 
                       c.nombre AS cliente, 
                       f.fecha, 
                       f.monto, 
                       e.nombre AS estado, 
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago,
                       COALESCE(SUM(df.cantidad), 0) AS total_articulos,
                       COALESCE(STRING_AGG(CONCAT(df.cantidad, 'x ', p.nombre), ', '), 'Sin ítems') AS resumen_items
                FROM facturas f
                INNER JOIN clientes c ON f.id_cliente = c.id
                INNER JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                LEFT JOIN detalle_facturas df ON df.id_factura = f.id
                LEFT JOIN productos p ON df.id_producto = p.id
                {where_sql}
                GROUP BY f.id, f.numero, c.nombre, f.fecha, f.monto, e.nombre, mp.nombre
                ORDER BY f.id DESC
                LIMIT %s OFFSET %s;
            '''
            params_datos = list(params) + [per_page, offset]
            cursor.execute(query_datos, tuple(params_datos))
            facturas_db = cursor.fetchall()
            cursor.close()
        except Exception as e:
            flash(f"Error al listar facturas: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión a la base de datos.", "danger")

    return render_template(
        'facturacion.html', 
        facturas=facturas_db, 
        sistema=SISTEMA_INFO,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
        q=q
    )


# 2. AGREGAR FACTURA MANUALMENTE (ADMIN / OPERADOR - SOLO FACTURAS PAGADAS)
@app.route('/facturacion/formulario', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def formulario_facturacion():
    conn = obtener_conexion()
    if not conn:
        flash('Error al conectar con la base de datos.', 'danger')
        return redirect(url_for('facturacion'))

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nombre, ruc FROM clientes WHERE activo = TRUE ORDER BY nombre ASC;')
        clientes_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM metodos_pago ORDER BY id ASC;')
        metodos_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE activo = TRUE AND stock > 0 ORDER BY nombre ASC;')
        filas_productos = cursor.fetchall()
        productos_bd = [
            {
                'id': extraer_columna(p, 'id', 0),
                'nombre': str(extraer_columna(p, 'nombre', 1)),
                'precio': float(extraer_columna(p, 'precio', 2, 0.0)),
                'stock': int(extraer_columna(p, 'stock', 3, 0))
            }
            for p in filas_productos
        ]

        form = FacturacionForm()
        form.cliente.choices = [
            (
                extraer_columna(c, 'id', 0), 
                f"{extraer_columna(c, 'nombre', 1)} - {extraer_columna(c, 'ruc', 2) or 'S/RUC'}"
            ) 
            for c in clientes_bd
        ]

        if form.validate_on_submit():
            numero = form.numero.data.strip().upper()
            fecha = form.fecha.data
            id_cliente = form.cliente.data
            id_estado = 1  # Emisión oficial confirmada (PAGADA)

            metodo_input = request.form.get('id_metodo_pago', '1')
            try:
                id_metodo_pago = int(metodo_input)
            except (ValueError, TypeError):
                id_metodo_pago = 1

            prod_ids = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            precios = request.form.getlist('precio[]')

            if not prod_ids:
                flash('Debe seleccionar al menos un producto activo para generar la factura.', 'warning')
                cursor.close()
                return render_template(
                    'formulario_facturacion.html', 
                    form=form, 
                    sistema=SISTEMA_INFO, 
                    titulo="Nueva Factura", 
                    productos_lista=productos_bd, 
                    metodos_lista=metodos_bd
                )

            items_validos = []
            total_acumulado = 0.0

            for p_id, cant_str, prec_str in zip(prod_ids, cantidades, precios):
                if not p_id or str(p_id).strip() == '':
                    continue
                cant = int(cant_str)
                prec = float(prec_str)

                cursor.execute('SELECT nombre, stock FROM productos WHERE id = %s AND activo = TRUE FOR UPDATE;', (int(p_id),))
                prod_info = cursor.fetchone()
                stock_real = int(extraer_columna(prod_info, 'stock', 1, 0))
                nom_prod = str(extraer_columna(prod_info, 'nombre', 0, 'Producto'))

                if not prod_info or cant > stock_real:
                    conn.rollback()
                    flash(f"Stock insuficiente para '{nom_prod}'. Disponible: {stock_real}, solicitado: {cant}.", 'danger')
                    cursor.close()
                    return render_template(
                        'formulario_facturacion.html', 
                        form=form, 
                        sistema=SISTEMA_INFO, 
                        titulo="Nueva Factura", 
                        productos_lista=productos_bd, 
                        metodos_lista=metodos_bd
                    )

                subtotal = round(cant * prec, 2)
                total_acumulado += subtotal
                items_validos.append({
                    'id_producto': int(p_id),
                    'cantidad': cant,
                    'precio': prec,
                    'subtotal': subtotal
                })

            # 1. Insertar Cabecera de Factura
            cursor.execute('''
                INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago, created_by, activo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id;
            ''', (numero, fecha, total_acumulado, id_cliente, id_estado, id_metodo_pago, current_user.usuario))

            nueva_fac = cursor.fetchone()
            id_factura = extraer_columna(nueva_fac, 'id', 0)

            # 2. Insertar Detalle (El Trigger de la base de datos descuenta el stock una única vez)
            for item in items_validos:
                cursor.execute('''
                    INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (id_factura, item['id_producto'], item['cantidad'], item['precio'], item['subtotal']))

            conn.commit()
            cursor.close()
            flash(f'Factura {numero} emitida y registrada exitosamente.', 'success')
            return redirect(url_for('facturacion'))

        cursor.close()
        return render_template(
            'formulario_facturacion.html', 
            form=form, 
            sistema=SISTEMA_INFO, 
            titulo="Nueva Factura", 
            productos_lista=productos_bd, 
            metodos_lista=metodos_bd, 
            detalles_guardados=[]
        )

    except Exception as e:
        conn.rollback()
        error_msg = str(e)
        if 'facturas_numero_key' in error_msg or 'unique constraint' in error_msg.lower():
            flash(f'El número de comprobante ya existe. Asigne un nuevo número correlativo.', 'warning')
        elif 'productos_stock_check' in error_msg:
            flash('Error de inventario: La cantidad solicitada supera las existencias físicas disponibles.', 'danger')
        else:
            flash(f'Error al procesar la factura: {e}', 'danger')
        return redirect(url_for('facturacion'))
    finally:
        conn.close()


# 3. MODIFICAR FACTURA (ADMIN / OPERADOR - PERSISTENCIA DE ESTADO Y CONSULTA NOMINAL)
@app.route('/facturacion/editar/<numero>', methods=['GET', 'POST'])
@login_required
@roles_requeridos('admin', 'operador')
def editar_factura(numero):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('facturacion'))

    try:
        cursor = conn.cursor()

        # Consulta con nombres de columna explícitos para evitar desajustes posicionales
        if str(numero).isdigit():
            cursor.execute('''
                SELECT id, numero, fecha, monto, id_cliente, id_estado, id_metodo_pago 
                FROM facturas WHERE id = %s AND activo = TRUE;
            ''', (int(numero),))
        else:
            cursor.execute('''
                SELECT id, numero, fecha, monto, id_cliente, id_estado, id_metodo_pago 
                FROM facturas WHERE numero = %s AND activo = TRUE;
            ''', (numero,))
        
        factura = cursor.fetchone()

        if not factura:
            flash('Factura no encontrada o dada de baja.', 'warning')
            cursor.close()
            return redirect(url_for('facturacion'))

        fac_id = extraer_columna(factura, 'id', 0)
        fac_num = extraer_columna(factura, 'numero', 1)
        fac_fecha = extraer_columna(factura, 'fecha', 2)
        fac_monto = extraer_columna(factura, 'monto', 3)
        fac_id_cliente = extraer_columna(factura, 'id_cliente', 4)
        estado_anterior_id = int(extraer_columna(factura, 'id_estado', 5, 1))
        fac_id_metodo = int(extraer_columna(factura, 'id_metodo_pago', 6, 1))

        cursor.execute('SELECT id, nombre, ruc FROM clientes WHERE activo = TRUE ORDER BY nombre ASC;')
        clientes_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre FROM metodos_pago ORDER BY id ASC;')
        metodos_bd = cursor.fetchall()

        cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE activo = TRUE ORDER BY nombre ASC;')
        productos_bd = [
            {
                'id': extraer_columna(p, 'id', 0),
                'nombre': str(extraer_columna(p, 'nombre', 1)),
                'precio': float(extraer_columna(p, 'precio', 2, 0.0)),
                'stock': int(extraer_columna(p, 'stock', 3, 0))
            }
            for p in cursor.fetchall()
        ]

        # Extraer líneas facturadas con stock compensado
        cursor.execute('''
            SELECT d.id_producto, p.nombre, d.precio_unitario, d.cantidad, d.subtotal, p.stock
            FROM detalle_facturas d
            INNER JOIN productos p ON d.id_producto = p.id
            WHERE d.id_factura = %s;
        ''', (fac_id,))
        detalles_bd = [
            {
                'id_producto': extraer_columna(d, 'id_producto', 0),
                'nombre': extraer_columna(d, 'nombre', 1),
                'precio': float(extraer_columna(d, 'precio_unitario', 2, 0.0)),
                'cantidad': int(extraer_columna(d, 'cantidad', 3, 0)),
                'subtotal': float(extraer_columna(d, 'subtotal', 4, 0.0)),
                'stock': int(extraer_columna(d, 'stock', 5, 0)) + (int(extraer_columna(d, 'cantidad', 3, 0)) if estado_anterior_id != 3 else 0)
            }
            for d in cursor.fetchall()
        ]

        form = FacturacionForm()
        form.cliente.choices = [
            (extraer_columna(c, 'id', 0), f"{extraer_columna(c, 'nombre', 1)} - {extraer_columna(c, 'ruc', 2) or 'S/RUC'}")
            for c in clientes_bd
        ]

        if request.method == 'GET':
            form.numero.data = fac_num
            form.fecha.data = fac_fecha
            form.monto.data = fac_monto
            form.cliente.data = fac_id_cliente
            form.estado.data = estado_anterior_id

            cursor.close()
            return render_template(
                'formulario_facturacion.html', 
                form=form, 
                sistema=SISTEMA_INFO, 
                titulo="Editar Factura", 
                productos_lista=productos_bd, 
                metodos_lista=metodos_bd,
                detalles_guardados=detalles_bd,
                factura={'id_metodo_pago': fac_id_metodo}
            )

        elif form.validate_on_submit():
            nuevo_numero = form.numero.data.strip().upper()
            fecha = form.fecha.data
            id_cliente = form.cliente.data
            nuevo_estado_id = int(form.estado.data)

            metodo_input = request.form.get('id_metodo_pago', str(fac_id_metodo))
            try:
                nuevo_metodo_pago = int(metodo_input)
            except (ValueError, TypeError):
                nuevo_metodo_pago = fac_id_metodo

            prod_ids = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            precios = request.form.getlist('precio[]')

            # 1. Devolver el inventario anterior si la factura no estaba ya anulada
            if estado_anterior_id != 3:
                cursor.execute('SELECT id_producto, cantidad FROM detalle_facturas WHERE id_factura = %s;', (fac_id,))
                for it in cursor.fetchall():
                    p_ant = extraer_columna(it, 'id_producto', 0)
                    c_ant = extraer_columna(it, 'cantidad', 1)
                    cursor.execute('UPDATE productos SET stock = stock + %s WHERE id = %s;', (c_ant, p_ant))

            # 2. Reemplazar líneas de detalle
            cursor.execute('DELETE FROM detalle_facturas WHERE id_factura = %s;', (fac_id,))

            total_acumulado = 0.0
            for p_id, cant_str, prec_str in zip(prod_ids, cantidades, precios):
                if not p_id or str(p_id).strip() == '':
                    continue
                cant = int(cant_str)
                prec = float(prec_str)
                subt = round(cant * prec, 2)
                total_acumulado += subt

                cursor.execute('''
                    INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s);
                ''', (fac_id, int(p_id), cant, prec, subt))

                # Descontar stock solo si el nuevo estado es Pagada (1) o Pendiente (2)
                if nuevo_estado_id != 3:
                    cursor.execute('UPDATE productos SET stock = stock - %s WHERE id = %s;', (cant, int(p_id)))

            monto_final = total_acumulado if prod_ids else float(form.monto.data or 0.0)

            # 3. Actualización de factura persistiendo id_estado
            cursor.execute('''
                UPDATE facturas
                SET numero = %s, 
                    fecha = %s, 
                    monto = %s, 
                    id_cliente = %s, 
                    id_estado = %s, 
                    id_metodo_pago = %s, 
                    modified_by = %s
                WHERE id = %s;
            ''', (nuevo_numero, fecha, monto_final, id_cliente, nuevo_estado_id, nuevo_metodo_pago, current_user.usuario, fac_id))

            conn.commit()
            cursor.close()
            flash('Factura actualizada y estado sincronizado correctamente.', 'success')
            return redirect(url_for('facturacion'))

        else:
            for campo, errores in form.errors.items():
                for err in errores:
                    flash(f"Error en {campo}: {err}", "danger")

        cursor.close()
        return render_template(
            'formulario_facturacion.html', 
            form=form, 
            sistema=SISTEMA_INFO, 
            titulo="Editar Factura", 
            productos_lista=productos_bd, 
            metodos_lista=metodos_bd,
            detalles_guardados=detalles_bd,
            factura={'id_metodo_pago': fac_id_metodo}
        )

    except Exception as e:
        conn.rollback()
        flash(f'Error al modificar la factura: {e}', 'danger')
        return redirect(url_for('facturacion'))
    finally:
        conn.close()


# 4. ELIMINAR / ANULAR FACTURA (SOFT DELETE CON REINTEGRO AUTOMÁTICO)
@app.route('/facturacion/eliminar/<numero>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_factura(numero):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            if str(numero).isdigit():
                cursor.execute('SELECT id, numero, id_estado FROM facturas WHERE id = %s AND activo = TRUE;', (int(numero),))
            else:
                cursor.execute('SELECT id, numero, id_estado FROM facturas WHERE numero = %s AND activo = TRUE;', (numero,))
            fac_row = cursor.fetchone()

            if not fac_row:
                flash('La factura no existe o ya fue anulada.', 'warning')
                cursor.close()
                return redirect(url_for('facturacion'))

            fac_id = fac_row[0]
            fac_num = fac_row[1]
            estado_previo = int(fac_row[2])

            # Solo reintegrar stock si no estaba ya anulada (3)
            if estado_previo != 3:
                cursor.execute('SELECT id_producto, cantidad FROM detalle_facturas WHERE id_factura = %s;', (fac_id,))
                detalles = cursor.fetchall()
                for d in detalles:
                    pid = d[0]
                    cant = d[1]
                    cursor.execute('UPDATE productos SET stock = stock + %s, modified_by = %s WHERE id = %s;', 
                                   (cant, current_user.usuario, pid))

            cursor.execute('''
                UPDATE facturas 
                SET activo = FALSE, id_estado = 3, modified_by = %s 
                WHERE id = %s;
            ''', (current_user.usuario, fac_id))

            conn.commit()
            cursor.close()
            flash(f'Factura {fac_num} anulada con éxito y stock devuelto al inventario.', 'info')
        except Exception as e:
            conn.rollback()
            flash(f'No se pudo anular la factura: {e}', 'danger')
        finally:
            conn.close()

    return redirect(url_for('facturacion'))


# 5. HISTORIAL DE COMPRAS DEL CLIENTE (CON DETALLE CONSOLIDADO DE PRODUCTOS)
@app.route('/mis-facturas')
@login_required
def mis_facturas():
    conn = obtener_conexion()
    facturas_usuario = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, 
                       f.numero, 
                       f.fecha, 
                       f.monto, 
                       f.id_estado, 
                       COALESCE(e.nombre, 'Pendiente') AS estado,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago,
                       COALESCE(SUM(df.cantidad), 0) AS total_articulos,
                       COALESCE(STRING_AGG(CONCAT(df.cantidad, 'x ', p.nombre), ', '), 'Sin ítems') AS resumen_items
                FROM facturas f
                INNER JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                LEFT JOIN detalle_facturas df ON df.id_factura = f.id
                LEFT JOIN productos p ON df.id_producto = p.id
                WHERE c.usuario_id = %s AND f.activo = TRUE
                GROUP BY f.id, f.numero, f.fecha, f.monto, f.id_estado, e.nombre, mp.nombre
                ORDER BY f.id DESC;
            ''', (int(current_user.id),))
            
            filas = cursor.fetchall()
            cursor.close()

            for fila in filas:
                facturas_usuario.append({
                    'id': extraer_columna(fila, 'id', 0),
                    'numero': extraer_columna(fila, 'numero', 1),
                    'fecha': extraer_columna(fila, 'fecha', 2),
                    'monto': float(extraer_columna(fila, 'monto', 3, 0.0)),
                    'id_estado': extraer_columna(fila, 'id_estado', 4),
                    'estado': extraer_columna(fila, 'estado', 5),
                    'metodo_pago': extraer_columna(fila, 'metodo_pago', 6),
                    'total_articulos': int(extraer_columna(fila, 'total_articulos', 7, 0)),
                    'resumen_items': str(extraer_columna(fila, 'resumen_items', 8, 'Sin ítems'))
                })

        except Exception as e:
            flash(f"Error al obtener tus compras: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión con la base de datos.", "danger")

    return render_template('mis_facturas.html', facturas=facturas_usuario, sistema=SISTEMA_INFO)

# 6. VER COMPROBANTE / IMPRIMIR FACTURA (SOLO FACTURAS PAGADAS)
@app.route('/facturacion/descargar/<int:id_factura>')
@login_required
def descargar_factura(id_factura):
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('dashboard'))

    cursor = None
    try:
        cursor = conn.cursor()

        # Validación con respecto al rol y obtención del estado real de la factura
        if current_user.rol == 'usuario':
            cursor.execute('''
                SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado, 
                       e.nombre AS estado,
                       COALESCE(c.nombre, 'Consumidor Final') AS cliente, 
                       c.email, c.ruc, c.telefono,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago
                FROM facturas f
                LEFT JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                WHERE f.id = %s AND c.usuario_id = %s AND f.activo = TRUE;
            ''', (id_factura, int(current_user.id)))
        else:
            cursor.execute('''
                SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado, 
                       e.nombre AS estado,
                       COALESCE(c.nombre, 'Consumidor Final') AS cliente, 
                       c.email, c.ruc, c.telefono,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago
                FROM facturas f
                LEFT JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                WHERE f.id = %s AND f.activo = TRUE;
            ''', (id_factura,))

        fila_fac = cursor.fetchone()

        if not fila_fac:
            flash("Comprobante no encontrado o acceso denegado.", "danger")
            return redirect(url_for('mis_facturas' if current_user.rol == 'usuario' else 'facturacion'))

        id_estado = int(extraer_columna(fila_fac, 'id_estado', 4, 0))
        nombre_estado = str(extraer_columna(fila_fac, 'estado', 5, '')).strip()
        num_factura = extraer_columna(fila_fac, 'numero', 1)

        # Regla estricta de producción: Solo facturas PAGADAS (id_estado = 1)
        if id_estado != 1 or nombre_estado.lower() != 'pagada':
            estado_aviso = nombre_estado if nombre_estado else "Pendiente de Pago"
            flash(
                f"Bloqueo comercial: La factura {num_factura} se encuentra en estado '{estado_aviso}'. "
                f"Por control contable, únicamente se emiten comprobantes oficiales de pagos liquidados.", 
                "warning"
            )
            return redirect(url_for('mis_facturas' if current_user.rol == 'usuario' else 'facturacion'))

        factura_dict = {
            'id': extraer_columna(fila_fac, 'id', 0),
            'numero': num_factura,
            'fecha': extraer_columna(fila_fac, 'fecha', 2),
            'monto': float(extraer_columna(fila_fac, 'monto', 3, 0.0)),
            'estado': 'Pagada',
            'cliente': extraer_columna(fila_fac, 'cliente', 6),
            'email': extraer_columna(fila_fac, 'email', 7),
            'ruc': extraer_columna(fila_fac, 'ruc', 8),
            'telefono': extraer_columna(fila_fac, 'telefono', 9),
            'metodo_pago': extraer_columna(fila_fac, 'metodo_pago', 10)
        }

        cursor.execute('''
            SELECT COALESCE(p.nombre, 'Producto General') AS nombre, 
                   df.cantidad, 
                   df.precio_unitario, 
                   ROUND(df.cantidad * df.precio_unitario, 2) AS subtotal
            FROM detalle_facturas df
            LEFT JOIN productos p ON df.id_producto = p.id
            WHERE df.id_factura = %s;
        ''', (factura_dict['id'],))
        
        filas_detalles = cursor.fetchall()

        detalles_lista = [
            {
                'nombre': extraer_columna(d, 'nombre', 0),
                'cantidad': int(extraer_columna(d, 'cantidad', 1, 0)),
                'precio': float(extraer_columna(d, 'precio_unitario', 2, 0.0)),
                'subtotal': float(extraer_columna(d, 'subtotal', 3, 0.0))
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
        if cursor:
            cursor.close()
        conn.close()


# 6.1 CAMBIAR ESTADO DE FACTURA (ADMIN Y OPERADOR)
@app.route('/facturacion/cambiar-estado/<int:id_factura>', methods=['POST'])
@login_required
def cambiar_estado_factura(id_factura):
    if current_user.rol not in ['admin', 'operador']:
        flash('No tiene permisos para modificar el estado de las facturas.', 'danger')
        return redirect(url_for('dashboard'))

    # Corregido para leer 'nuevo_estado' enviado por los selectores del dashboard y facturación
    nuevo_estado = request.form.get('nuevo_estado')
    try:
        nuevo_estado_id = int(nuevo_estado)
    except (ValueError, TypeError):
        flash('Estado de factura inválido.', 'warning')
        return redirect(request.referrer or url_for('dashboard'))

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT numero, id_estado FROM facturas WHERE id = %s AND activo = TRUE;', (id_factura,))
        factura = cursor.fetchone()
        if not factura:
            flash('Factura no encontrada o inactiva.', 'warning')
            cursor.close()
            return redirect(request.referrer or url_for('dashboard'))

        num_factura = extraer_columna(factura, 'numero', 0)
        estado_anterior_id = int(extraer_columna(factura, 'id_estado', 1, 0))

        # Reintegrar inventario únicamente si cambia a Anulada (3) y no estaba anulada previamente
        if nuevo_estado_id == 3 and estado_anterior_id != 3:
            cursor.execute('SELECT id_producto, cantidad FROM detalle_facturas WHERE id_factura = %s;', (id_factura,))
            detalles = cursor.fetchall()
            for d in detalles:
                pid = extraer_columna(d, 'id_producto', 0)
                cant = extraer_columna(d, 'cantidad', 1)
                cursor.execute('UPDATE productos SET stock = stock + %s, modified_by = %s WHERE id = %s;', 
                               (cant, current_user.usuario, pid))

        cursor.execute('''
            UPDATE facturas 
            SET id_estado = %s, modified_by = %s 
            WHERE id = %s;
        ''', (nuevo_estado_id, current_user.usuario, id_factura))

        conn.commit()
        cursor.close()

        if nuevo_estado_id == 1:
            flash(f'¡Cobro validado! La factura {num_factura} quedó registrada como PAGADA.', 'success')
        elif nuevo_estado_id == 3:
            flash(f'La factura {num_factura} fue ANULADA y el stock reincorporado al catálogo.', 'info')
        else:
            flash(f'Estado de la factura {num_factura} actualizado correctamente.', 'primary')

    except Exception as e:
        conn.rollback()
        flash(f'Error al cambiar el estado de la factura: {e}', 'danger')
    finally:
        conn.close()

    # Redirige de vuelta a la página de origen (Dashboard o Facturación) de manera fluida
    return redirect(request.referrer or url_for('dashboard'))


# 7. GESTIÓN DEL CARRITO EN SESIÓN Y FACTURACIÓN DIRECTA PAGADA

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
        cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE id = %s AND activo = TRUE;', (id_producto,))
        prod = cursor.fetchone()
        cursor.close()

        if not prod:
            flash('Producto no disponible o dado de baja.', 'warning')
            return redirect(url_for('productos'))

        nombre_prod = extraer_columna(prod, 'nombre', 1)
        precio_prod = float(extraer_columna(prod, 'precio', 2, 0.0))
        stock_prod = int(extraer_columna(prod, 'stock', 3, 0))

        if 'carrito' not in session:
            session['carrito'] = {}

        carrito = session['carrito']
        prod_id_str = str(id_producto)
        cant_actual = carrito.get(prod_id_str, {}).get('cantidad', 0)
        nueva_cant = cant_actual + cantidad

        if nueva_cant > stock_prod:
            flash(f'No es posible solicitar {nueva_cant} unidades. Stock disponible: {stock_prod}.', 'warning')
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


# 7.2 ACTUALIZAR CANTIDAD (+, -, o manual)
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
        cursor.execute('SELECT stock FROM productos WHERE id = %s AND activo = TRUE;', (id_producto,))
        prod = cursor.fetchone()
        cursor.close()

        stock_disponible = int(extraer_columna(prod, 'stock', 0, 0))

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


# 7.3 VER CARRITO
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


# 7.5 VACIAR CARRITO
@app.route('/carrito/vaciar', methods=['POST'])
@login_required
def vaciar_carrito():
    session.pop('carrito', None)
    flash('Se ha vaciado el carrito de compras.', 'info')
    return redirect(url_for('ver_carrito'))

# 7.6 FINALIZAR COMPRA (AUTORIZACIÓN AUTOMÁTICA PARA TARJETA, PENDIENTE PARA OTROS)
@app.route('/carrito/finalizar-compra', methods=['POST'])
@login_required
def finalizar_compra():
    carrito = session.get('carrito', {})
    if not carrito:
        flash('El carrito está vacío. Agregue productos antes de continuar.', 'warning')
        return redirect(url_for('productos'))

    metodo_pago_val = request.form.get('metodo_pago', '1')
    try:
        id_metodo_pago = int(metodo_pago_val)
    except ValueError:
        id_metodo_pago = 1

    # REGLA DE PASARELA PROFESIONAL:
    # - Si paga con Tarjeta (ID 3): Se aprueba de inmediato -> Pagada (id_estado = 1)
    # - Si paga con Efectivo (ID 1) o Transferencia (ID 2): Requiere validación -> Pendiente (id_estado = 2)
    if id_metodo_pago == 3:
        tipo_tarjeta = request.form.get('tipo_tarjeta', 'debito')
        num_tarjeta = request.form.get('num_tarjeta', '').strip()
        titular = request.form.get('titular_tarjeta', '').strip()
        exp = request.form.get('exp_tarjeta', '').strip()
        cvv = request.form.get('cvv_tarjeta', '').strip()

        if not num_tarjeta or len(num_tarjeta) < 12 or not titular or not exp or not cvv:
            flash('Error de pasarela: Debe completar todos los datos de su tarjeta de forma válida.', 'danger')
            return redirect(url_for('ver_carrito'))

        if tipo_tarjeta == 'credito':
            diferido_meses = request.form.get('diferido_meses', '3')

        id_estado_factura = 1  # 1 = Pagada (Autorizada por pasarela de tarjeta)
        mensaje_exito = '¡Pago con tarjeta autorizado con éxito! Se ha emitido su factura oficial.'
    else:
        id_estado_factura = 2  # 2 = Pendiente de validación manual
        mensaje_exito = '¡Pedido registrado con éxito! Su orden se encuentra en estado Pendiente de validación.'

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('ver_carrito'))

    try:
        cursor = conn.cursor()

        # 1. Obtener cliente_id vinculado
        cursor.execute('SELECT id FROM clientes WHERE usuario_id = %s AND activo = TRUE LIMIT 1;', (int(current_user.id),))
        cliente = cursor.fetchone()
        if not cliente:
            flash('No se encontró un perfil de cliente activo asociado a su cuenta.', 'danger')
            cursor.close()
            return redirect(url_for('productos'))

        id_cliente = extraer_columna(cliente, 'id', 0)

        # 2. Validar stock en tiempo real
        monto_total = 0.0
        items_a_procesar = []

        for prod_id_str, item in carrito.items():
            id_prod = int(prod_id_str)
            cant_solicitada = int(item['cantidad'])

            cursor.execute('SELECT nombre, precio, stock FROM productos WHERE id = %s AND activo = TRUE FOR UPDATE;', (id_prod,))
            prod_db = cursor.fetchone()

            if not prod_db:
                flash(f'El producto "{item["nombre"]}" ya no está disponible en catálogo.', 'danger')
                conn.rollback()
                cursor.close()
                return redirect(url_for('ver_carrito'))

            stock_disponible = int(extraer_columna(prod_db, 'stock', 2, 0))
            precio_real = float(extraer_columna(prod_db, 'precio', 1, 0.0))
            nombre_real = extraer_columna(prod_db, 'nombre', 0, '')

            if cant_solicitada > stock_disponible:
                flash(f'Stock insuficiente para "{nombre_real}". Disponible: {stock_disponible}.', 'warning')
                conn.rollback()
                cursor.close()
                return redirect(url_for('ver_carrito'))

            subtotal_item = round(precio_real * cant_solicitada, 2)
            monto_total += subtotal_item
            items_a_procesar.append((id_prod, cant_solicitada, precio_real, subtotal_item))

        # 3. Secuencial de Factura seguro
        anio_actual = datetime.now().year
        prefijo = f"FAC-{anio_actual}-"

        cursor.execute('SELECT numero FROM facturas WHERE numero LIKE %s ORDER BY id DESC LIMIT 50;', (f"{prefijo}%",))
        filas_numeros = cursor.fetchall()
        max_secuencial = 0
        for f_num in filas_numeros:
            cadena_num = extraer_columna(f_num, 'numero', 0, '')
            partes = cadena_num.split('-')
            if len(partes) >= 3 and partes[-1].isdigit():
                val = int(partes[-1])
                if val > max_secuencial:
                    max_secuencial = val

        numero_factura = f"{prefijo}{max_secuencial + 1:03d}"

        # 4. Insertar Factura con estado dinámico (Pagada si es tarjeta, Pendiente si es transferencia/efectivo)
        cursor.execute('''
            INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago, created_by, activo)
            VALUES (%s, CURRENT_DATE, %s, %s, %s, %s, %s, TRUE)
            RETURNING id;
        ''', (numero_factura, monto_total, id_cliente, id_estado_factura, id_metodo_pago, current_user.usuario))

        res_fac = cursor.fetchone()
        id_factura = extraer_columna(res_fac, 'id', 0)

        # 5. Insertar Detalle (el Trigger en PostgreSQL descuenta el inventario automáticamente)
        for id_prod, cant, precio, subtotal in items_a_procesar:
            cursor.execute('''
                INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (%s, %s, %s, %s, %s);
            ''', (id_factura, id_prod, cant, precio, subtotal))

        conn.commit()
        cursor.close()

        session.pop('carrito', None)
        flash(mensaje_exito, 'success')
        return redirect(url_for('mis_facturas'))

    except Exception as e:
        conn.rollback()
        flash(f'Error al procesar el pedido: {e}', 'danger')
        return redirect(url_for('ver_carrito'))
    finally:
        conn.close()

# 7.7 AGREGAR MÚLTIPLES PRODUCTOS DESDE EL CATÁLOGO
@app.route('/carrito/agregar-multiples', methods=['POST'])
@login_required
def agregar_multiples_carrito():
    ids_seleccionados = request.form.getlist('productos_seleccionados')
    
    if not ids_seleccionados:
        flash('No ha seleccionado ningún producto para agregar al carrito.', 'warning')
        return redirect(url_for('productos'))

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('productos'))

    try:
        cursor = conn.cursor()
        if 'carrito' not in session:
            session['carrito'] = {}
        carrito = session['carrito']

        agregados_count = 0

        for id_str in ids_seleccionados:
            try:
                id_producto = int(id_str)
                cant_solicitada = int(request.form.get(f'cantidad_{id_producto}', 1))
                if cant_solicitada < 1:
                    cant_solicitada = 1
            except ValueError:
                continue

            cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE id = %s AND activo = TRUE;', (id_producto,))
            prod = cursor.fetchone()

            if prod:
                nombre_prod = extraer_columna(prod, 'nombre', 1)
                precio_prod = float(extraer_columna(prod, 'precio', 2, 0.0))
                stock_prod = int(extraer_columna(prod, 'stock', 3, 0))

                prod_id_str = str(id_producto)
                cant_actual = carrito.get(prod_id_str, {}).get('cantidad', 0)
                nueva_cant = cant_actual + cant_solicitada

                if nueva_cant > stock_prod:
                    flash(f'Stock insuficiente para "{nombre_prod}". Máximo disponible: {stock_prod}. Se omitió este ítem.', 'warning')
                    continue

                carrito[prod_id_str] = {
                    'id': id_producto,
                    'nombre': nombre_prod,
                    'precio': precio_prod,
                    'cantidad': nueva_cant,
                    'subtotal': round(precio_prod * nueva_cant, 2)
                }
                agregados_count += 1

        cursor.close()
        session['carrito'] = carrito
        session.modified = True

        if agregados_count > 0:
            flash(f'¡Se agregaron con éxito {agregados_count} producto(s) seleccionados al carrito!', 'success')
        
        return redirect(url_for('ver_carrito'))

    except Exception as e:
        flash(f'Error al procesar la selección múltiple: {e}', 'danger')
        return redirect(url_for('productos'))
    finally:
        conn.close()

# INICIO DE LA APLICACIÓN
if __name__ == '__main__':
    app.run(debug=True)