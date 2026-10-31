import os
import io
import csv
import json
import uuid
import shutil
import random
import math
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, Response, redirect, render_template, request, url_for, flash, session, send_file, jsonify

# IMPORTACIONES DE AUTENTICACIÓN
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

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

# Utilidad de paginación estandarizada y generador RIDE PDF (SRI)
from utils.paginacion import Paginacion
from utils.factura_pdf import generar_pdf_ride_sri

from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'techmanager_dev_fallback_key_2026')

# --- CONFIGURACIÓN DE SUBIDA DE IMÁGENES DE PRODUCTOS ---
UPLOAD_FOLDER_PRODUCTOS = os.path.join(app.root_path, 'static', 'uploads', 'productos')
EXTENSIONES_IMAGEN_PERMITIDAS = {'.png', '.jpg', '.jpeg', '.webp'}
app.config['UPLOAD_FOLDER_PRODUCTOS'] = UPLOAD_FOLDER_PRODUCTOS
os.makedirs(UPLOAD_FOLDER_PRODUCTOS, exist_ok=True)

# Asegurar imagen por defecto en static/uploads/productos/default_producto.png
_ruta_default_prod = os.path.join(UPLOAD_FOLDER_PRODUCTOS, 'default_producto.png')
_ruta_emblem_fallback = os.path.join(app.root_path, 'static', 'img', 'TechManager_Emblem.png')
if not os.path.exists(_ruta_default_prod) and os.path.exists(_ruta_emblem_fallback):
    try:
        shutil.copyfile(_ruta_emblem_fallback, _ruta_default_prod)
    except Exception:
        pass


_FORTINET_RECUPERADO_MEM = False


def asegurar_columna_imagen_productos(conn):
    """Garantiza que la tabla productos tenga la columna imagen VARCHAR(255) y reactiva Fortinet 40F."""
    global _FORTINET_RECUPERADO_MEM
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS imagen VARCHAR(255) DEFAULT 'default_producto.png';
        """)
        if not _FORTINET_RECUPERADO_MEM:
            cur.execute("""
                UPDATE productos
                SET activo = TRUE, modified_by = 'admin'
                WHERE nombre ILIKE %s AND activo = FALSE;
            """, ('%Firewall Fortinet FortiGate 40F%',))
            _FORTINET_RECUPERADO_MEM = True
        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()


# Reactivar de inmediato 'Firewall Fortinet FortiGate 40F' al iniciar el módulo
_conn_init = obtener_conexion()
if _conn_init:
    try:
        asegurar_columna_imagen_productos(_conn_init)
    finally:
        _conn_init.close()


def guardar_imagen_producto(archivo_storage):
    """
    Valida y almacena la imagen subida para un producto en static/uploads/productos/.
    Retorna (nombre_archivo, mensaje_error).
    Si no se adjuntó archivo, retorna (None, None).
    """
    if not archivo_storage or not getattr(archivo_storage, 'filename', ''):
        return None, None

    nombre_original = secure_filename(archivo_storage.filename.strip())
    if not nombre_original:
        return None, 'El nombre del archivo de imagen no es válido.'

    _, ext = os.path.splitext(nombre_original)
    ext = ext.lower()
    if ext not in EXTENSIONES_IMAGEN_PERMITIDAS:
        return None, 'Formato de imagen no permitido. Solo se aceptan archivos .png, .jpg, .jpeg o .webp.'

    nombre_unico = secure_filename(f"prod_{uuid.uuid4().hex}{ext}")
    ruta_destino = os.path.join(app.config['UPLOAD_FOLDER_PRODUCTOS'], nombre_unico)
    os.makedirs(app.config['UPLOAD_FOLDER_PRODUCTOS'], exist_ok=True)
    archivo_storage.save(ruta_destino)
    return nombre_unico, None

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
            SELECT u.*, c.nombre AS cliente_nombre
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
            nombre_usr = extraer_columna(u, 'nombre', 6)
            nombre_cli = extraer_columna(u, 'cliente_nombre', 7)
            nombre_db = nombre_usr or nombre_cli or usuario_db

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
            es_peticion_json = (
                request.is_json
                or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('Accept', '')
            )
            if not current_user.is_authenticated:
                if es_peticion_json:
                    return jsonify({
                        "status": "error",
                        "mensaje": "Debe iniciar sesión para ejecutar esta operación.",
                        "afectados": 0
                    }), 401
                flash('Debe iniciar sesión para acceder a esta sección.', 'warning')
                return redirect(url_for('login'))

            if not current_user.tiene_rol(*roles_permitidos):
                if es_peticion_json:
                    return jsonify({
                        "status": "error",
                        "mensaje": "Acceso denegado: Se requiere rol de Administrador para ejecutar acciones en lote.",
                        "afectados": 0
                    }), 403
                flash('Acceso denegado: No tiene permisos suficientes para realizar esta acción.', 'danger')
                
                # Evita bucles de redirección según el rol
                if getattr(current_user, 'rol', 'usuario') == 'usuario':
                    return redirect(url_for('mis_facturas'))
                
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def extraer_ids_lote():
    """
    Extrae y sanitiza la lista de IDs enteros desde JSON (fetch/AJAX) o FormData.
    Retorna (lista_ids_unicos, payload_dict).
    """
    payload = request.get_json(silent=True) or {}
    raw_ids = []

    if isinstance(payload, dict) and 'ids' in payload:
        raw_ids = payload.get('ids') or []
    else:
        raw_ids = (
            request.form.getlist('ids')
            or request.form.getlist('ids[]')
            or request.form.getlist('productos_seleccionados')
        )
        if len(raw_ids) == 1 and isinstance(raw_ids[0], str) and ',' in raw_ids[0]:
            raw_ids = [x.strip() for x in raw_ids[0].split(',') if x.strip()]

    ids_limpios = []
    vistos = set()
    for valor in raw_ids:
        try:
            id_int = int(str(valor).strip())
            if id_int > 0 and id_int not in vistos:
                vistos.add(id_int)
                ids_limpios.append(id_int)
        except (ValueError, TypeError):
            continue

    return ids_limpios, payload


SISTEMA_INFO = {
    "nombre_sistema": "TechManager System",
    "periodo": "2026",
    "version": "2.0.0",
    "moneda": "$"
}

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
                asegurar_columnas_perfil_usuarios(conn)
                cursor.execute(
                    '''INSERT INTO usuarios (usuario, nombre, cedula, email, telefono, password, rol, activo) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE) RETURNING id;''',
                    (nombre_usuario, nombre_completo, ruc_cliente, email_usuario, telefono_cliente, hash_password, 'usuario')
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
        'facturas_validas': 0,
        'facturas_anuladas': 0,
        'total_ingresos': 0.0,
        'total_pendiente': 0.0,
        'productos_bajo_stock': 0,
        'facturas_recientes': [],
        'pendientes_recientes': []  # Mantenido por retrocompatibilidad
    }

    if not conn:
        return metricas

    try:
        asegurar_columna_imagen_productos(conn)
        cursor = conn.cursor()

        # Sincronizar integridad de comprobantes anulados (FAC-2026-003 y bajas previas) bajo regla SRI (id_estado = 3, activo = TRUE)
        cursor.execute('''
            UPDATE facturas
            SET id_estado = 3, activo = TRUE
            WHERE (numero = 'FAC-2026-003' AND (id_estado != 3 OR activo = FALSE))
               OR (activo = FALSE AND id_estado != 3);
        ''')
        if cursor.rowcount > 0:
            conn.commit()

        # 1. Contadores generales de entidades activas
        cursor.execute("SELECT COUNT(*) AS total FROM productos p WHERE p.activo = TRUE;")
        res = cursor.fetchone()
        metricas['total_productos'] = int(extraer_columna(res, 'total', 0, 0) or 0)

        cursor.execute("SELECT COUNT(*) AS total FROM clientes c WHERE c.activo = TRUE;")
        res = cursor.fetchone()
        metricas['total_clientes'] = int(extraer_columna(res, 'total', 0, 0) or 0)

        cursor.execute("SELECT COUNT(*) AS total FROM proveedores p WHERE p.activo = TRUE;")
        res = cursor.fetchone()
        metricas['total_proveedores'] = int(extraer_columna(res, 'total', 0, 0) or 0)

        cursor.execute('''
            SELECT 
                COUNT(*) FILTER (WHERE f.activo = TRUE) AS total,
                COUNT(*) FILTER (WHERE f.activo = TRUE AND f.id_estado NOT IN (3)) AS validas,
                COUNT(*) FILTER (WHERE f.id_estado = 3) AS anuladas
            FROM facturas f;
        ''')
        res_fac = cursor.fetchone()
        metricas['total_facturas'] = int(extraer_columna(res_fac, 'total', 0, 0) or 0)
        metricas['facturas_validas'] = int(extraer_columna(res_fac, 'validas', 1, 0) or 0)
        metricas['facturas_anuladas'] = int(extraer_columna(res_fac, 'anuladas', 2, 0) or 0)

        # 2. Volumen Total Recaudado: sumar únicamente facturas válidas y efectivamente cobradas (excluyendo ANULADAS id_estado = 3 y PENDIENTES)
        cursor.execute('''
            SELECT COALESCE(SUM(f.monto), 0) AS total_ingresos
            FROM facturas f
            LEFT JOIN estados_factura e ON f.id_estado = e.id
            WHERE f.activo = TRUE
              AND f.id_estado NOT IN (3)
              AND (
                  UPPER(COALESCE(e.nombre, '')) = 'PAGADA'
                  OR (e.nombre IS NULL AND f.id_estado IN (1, 2))
              );
        ''')
        res = cursor.fetchone()
        metricas['total_ingresos'] = float(extraer_columna(res, 'total_ingresos', 0, 0.0) or 0.0)

        # Total pendiente de cobro (facturas activas en estado Pendiente)
        cursor.execute('''
            SELECT COALESCE(SUM(f.monto), 0) AS total_pendiente
            FROM facturas f
            LEFT JOIN estados_factura e ON f.id_estado = e.id
            WHERE f.activo = TRUE
              AND f.id_estado NOT IN (3)
              AND UPPER(COALESCE(e.nombre, '')) LIKE 'PENDIENTE%';
        ''')
        res_pend = cursor.fetchone()
        metricas['total_pendiente'] = float(extraer_columna(res_pend, 'total_pendiente', 0, 0.0) or 0.0)

        # 3. Alertas de Inventario: únicamente productos con p.activo = TRUE y stock <= 5
        cursor.execute("SELECT COUNT(*) AS total FROM productos p WHERE p.activo = TRUE AND p.stock <= 5;")
        res = cursor.fetchone()
        metricas['productos_bajo_stock'] = int(extraer_columna(res, 'total', 0, 0) or 0)

        # 4. Últimas 5 facturas emitidas con JOIN a estados_factura y mapeo estricto de estado y clase visual
        cursor.execute('''
            SELECT f.id,
                   f.numero,
                   f.fecha,
                   f.monto,
                   f.id_estado,
                   f.activo,
                   COALESCE(c.nombre, 'Consumidor Final') AS cliente,
                   COALESCE(mp.nombre, 'Efectivo') AS metodo_pago,
                   COALESCE(
                       e.nombre,
                       CASE
                           WHEN f.id_estado = 3 OR f.activo = FALSE THEN 'Anulada'
                           WHEN f.id_estado = 2 THEN 'Pendiente'
                           ELSE 'Pagada'
                       END
                   ) AS estado
            FROM facturas f
            LEFT JOIN clientes c ON f.id_cliente = c.id
            LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
            LEFT JOIN estados_factura e ON f.id_estado = e.id
            ORDER BY f.id DESC
            LIMIT 5;
        ''')
        filas = cursor.fetchall()
        cursor.close()

        lista_ventas = []
        for f in filas:
            fac_id = int(extraer_columna(f, 'id', 0, 0) or 0)
            fac_num = str(extraer_columna(f, 'numero', 1, 'N/A') or 'N/A')
            fac_fecha = extraer_columna(f, 'fecha', 2, '')
            fac_monto = float(extraer_columna(f, 'monto', 3, 0.0) or 0.0)
            fac_id_estado = int(extraer_columna(f, 'id_estado', 4, 1) or 1)
            fac_activo = bool(extraer_columna(f, 'activo', 5, True))
            fac_cliente = str(extraer_columna(f, 'cliente', 6, 'Consumidor Final') or 'Consumidor Final')
            fac_metodo = str(extraer_columna(f, 'metodo_pago', 7, 'Efectivo') or 'Efectivo')
            fac_estado_raw = str(extraer_columna(f, 'estado', 8, 'Pagada') or 'Pagada').strip()

            # Determinación estricta del estado real y su clase visual (idéntica al módulo de facturación)
            if fac_id_estado == 3 or not fac_activo or 'anulad' in fac_estado_raw.lower():
                fac_id_estado = 3
                estado_real = 'Anulada'
                clase_badge = 'bg-danger-subtle text-danger border border-danger-subtle'
                icono_badge = 'bi-x-circle-fill'
            elif 'pendiente' in fac_estado_raw.lower() or (fac_id_estado == 2 and fac_estado_raw.lower() != 'pagada'):
                fac_id_estado = 2
                estado_real = 'Pendiente'
                clase_badge = 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'
                icono_badge = 'bi-clock-history'
            else:
                estado_real = 'Pagada'
                clase_badge = 'bg-success-subtle text-success border border-success-subtle'
                icono_badge = 'bi-check-circle-fill'

            lista_ventas.append({
                'id': fac_id,
                'numero': fac_num,
                'fecha': fac_fecha,
                'monto': fac_monto,
                'id_estado': fac_id_estado,
                'activo': fac_activo,
                'cliente': fac_cliente,
                'metodo_pago': fac_metodo,
                'estado': estado_real,
                'clase_badge': clase_badge,
                'icono_badge': icono_badge
            })

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

    # Normalización estricta de facturas recientes a diccionarios puros conservando estado y clase visual
    facturas_limpias = []
    raw_facturas = metricas.get('facturas_recientes', [])
    if isinstance(raw_facturas, (list, tuple)):
        for f in raw_facturas:
            if isinstance(f, dict):
                id_est = convertir_valor(f.get('id_estado'), int, 1)
                est_txt = str(f.get('estado', 'Pagada')).strip()
                if id_est == 3 or 'anulad' in est_txt.lower():
                    id_est = 3
                    est_txt = 'Anulada'
                    clase_b = 'bg-danger-subtle text-danger border border-danger-subtle'
                    icono_b = 'bi-x-circle-fill'
                elif 'pendiente' in est_txt.lower() or (id_est == 2 and est_txt.lower() != 'pagada'):
                    id_est = 2
                    est_txt = 'Pendiente'
                    clase_b = 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'
                    icono_b = 'bi-clock-history'
                else:
                    est_txt = 'Pagada'
                    clase_b = 'bg-success-subtle text-success border border-success-subtle'
                    icono_b = 'bi-check-circle-fill'

                facturas_limpias.append({
                    'id': convertir_valor(f.get('id'), int, 0),
                    'numero': str(f.get('numero', 'N/A')),
                    'fecha': str(f.get('fecha', '')),
                    'monto': convertir_valor(f.get('monto'), float, 0.0),
                    'id_estado': id_est,
                    'cliente': str(f.get('cliente', 'Consumidor Final')),
                    'metodo_pago': str(f.get('metodo_pago', 'Efectivo')),
                    'estado': est_txt,
                    'clase_badge': f.get('clase_badge', clase_b),
                    'icono_badge': f.get('icono_badge', icono_b)
                })
            elif isinstance(f, (list, tuple)):
                id_est = convertir_valor(f[4] if len(f) > 4 else 1, int, 1)
                est_txt = str(f[7] if len(f) > 7 else 'Pagada').strip()
                if id_est == 3 or 'anulad' in est_txt.lower():
                    id_est = 3
                    est_txt = 'Anulada'
                    clase_b = 'bg-danger-subtle text-danger border border-danger-subtle'
                    icono_b = 'bi-x-circle-fill'
                elif 'pendiente' in est_txt.lower() or (id_est == 2 and est_txt.lower() != 'pagada'):
                    id_est = 2
                    est_txt = 'Pendiente'
                    clase_b = 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'
                    icono_b = 'bi-clock-history'
                else:
                    est_txt = 'Pagada'
                    clase_b = 'bg-success-subtle text-success border border-success-subtle'
                    icono_b = 'bi-check-circle-fill'

                facturas_limpias.append({
                    'id': convertir_valor(f[0] if len(f) > 0 else 0, int, 0),
                    'numero': str(f[1] if len(f) > 1 else 'N/A'),
                    'fecha': str(f[2] if len(f) > 2 else ''),
                    'monto': convertir_valor(f[3] if len(f) > 3 else 0.0, float, 0.0),
                    'id_estado': id_est,
                    'cliente': str(f[5] if len(f) > 5 else 'Consumidor Final'),
                    'metodo_pago': str(f[6] if len(f) > 6 else 'Efectivo'),
                    'estado': est_txt,
                    'clase_badge': clase_b,
                    'icono_badge': icono_b
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
# 1. LISTADO (SELECT con LEFT JOIN, búsqueda, paginación y filtro por estado activo/inactivo/todos)
@app.route('/productos')
@login_required
def productos():
    conn = obtener_conexion()
    productos_db = []
    page = max(1, request.args.get('page', 1, type=int))
    q = request.args.get('q', '', type=str).strip()
    estado_param = request.args.get('estado', 'activos', type=str).strip().lower()

    # Solo el administrador puede alternar entre 'activos', 'inactivos' y 'todos'
    if getattr(current_user, 'rol', 'usuario') == 'admin':
        estado_filtro = estado_param if estado_param in ('activos', 'inactivos', 'todos') else 'activos'
    else:
        estado_filtro = 'activos'

    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    conteos_estado = {'activos': 0, 'inactivos': 0, 'todos': 0}

    if conn:
        try:
            asegurar_columna_imagen_productos(conn)
            cursor = conn.cursor()

            # Recuperación puntual solicitada: asegurar que 'Firewall Fortinet FortiGate 40F' con stock reintegrado esté activo
            if not session.get('_fortinet_40f_reactivado'):
                cursor.execute('''
                    UPDATE productos
                    SET activo = TRUE, modified_by = %s
                    WHERE nombre ILIKE %s AND activo = FALSE AND stock > 0;
                ''', (getattr(current_user, 'usuario', 'admin'), '%Firewall Fortinet FortiGate 40F%'))
                if cursor.rowcount > 0:
                    conn.commit()
                session['_fortinet_40f_reactivado'] = True

            # Conteos rápidos por estado para las pestañas del Administrador
            cursor.execute('''
                SELECT 
                    COUNT(*) FILTER (WHERE activo = TRUE) AS activos,
                    COUNT(*) FILTER (WHERE activo = FALSE) AS inactivos,
                    COUNT(*) AS todos
                FROM productos;
            ''')
            row_est = cursor.fetchone()
            if row_est:
                conteos_estado['activos'] = int(extraer_columna(row_est, 'activos', 0, 0) or 0)
                conteos_estado['inactivos'] = int(extraer_columna(row_est, 'inactivos', 1, 0) or 0)
                conteos_estado['todos'] = int(extraer_columna(row_est, 'todos', 2, 0) or 0)

            # Construcción dinámica de filtros según estado
            if estado_filtro == 'inactivos':
                where_sql = "WHERE p.activo = FALSE"
            elif estado_filtro == 'todos':
                where_sql = "WHERE 1=1"
            else:
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

            # a) Conteo total filtrado para paginación
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM productos p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            total_items = int(extraer_columna(row_count, 'total', 0, 0))

            # b) Consulta paginada con LIMIT y OFFSET (incluye imagen y estado activo)
            query_datos = f'''
                SELECT p.id, p.nombre, p.descripcion,
                       COALESCE(c.nombre, 'Sin categoría') AS categoria,
                       p.precio, p.stock,
                       COALESCE(NULLIF(TRIM(p.imagen), ''), 'default_producto.png') AS imagen,
                       p.activo
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

    paginador = Paginacion(
        items=productos_db,
        total_registros=total_items,
        pagina_actual=page,
        por_pagina=per_page
    )

    return render_template(
        'productos.html', 
        productos=paginador.items,
        paginador=paginador,
        sistema=SISTEMA_INFO,
        page=paginador.pagina_actual,
        total_pages=paginador.total_paginas,
        total_items=paginador.total_registros,
        q=q,
        estado_actual=estado_filtro,
        conteos_estado=conteos_estado
    )


# 2. AGREGAR (INSERT INTO con descripcion, imagen, created_by y commit)
@app.route('/productos/formulario', methods=['GET', 'POST'])
@app.route('/productos/crear', methods=['GET', 'POST'])
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
        asegurar_columna_imagen_productos(conn)
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

        # Recepción y validación de imagen desde request.files
        archivo_imagen = request.files.get('imagen')
        nombre_imagen, error_img = guardar_imagen_producto(archivo_imagen)
        if error_img:
            flash(error_img, 'warning')
            return render_template(
                'formulario_producto.html',
                form=form,
                sistema=SISTEMA_INFO,
                titulo="Nuevo Producto",
                imagen_actual='default_producto.png'
            )

        imagen_final = nombre_imagen or 'default_producto.png'

        conn = obtener_conexion()
        if conn:
            try:
                asegurar_columna_imagen_productos(conn)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO productos (nombre, precio, stock, id_categoria, id_marca, descripcion, imagen, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                ''', (nombre, precio, stock, id_categoria, id_marca, descripcion, imagen_final, current_user.usuario))
                conn.commit()
                cursor.close()
                flash('Producto registrado correctamente.', 'success')
                return redirect(url_for('productos'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar el producto: {e}', 'danger')
            finally:
                conn.close()

    return render_template(
        'formulario_producto.html',
        form=form,
        sistema=SISTEMA_INFO,
        titulo="Nuevo Producto",
        imagen_actual='default_producto.png'
    )


# 3. MODIFICAR (UPDATE WHERE con descripcion, imagen, modified_by y commit)
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
        asegurar_columna_imagen_productos(conn)
        cursor = conn.cursor()
        if getattr(current_user, 'rol', 'usuario') == 'admin':
            cursor.execute('SELECT * FROM productos WHERE id = %s;', (id,))
        else:
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

    imagen_actual = (producto.get('imagen') or '').strip() or 'default_producto.png'

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

        # Recepción y validación de nueva imagen (si se adjunta)
        archivo_imagen = request.files.get('imagen')
        nueva_imagen, error_img = guardar_imagen_producto(archivo_imagen)
        if error_img:
            flash(error_img, 'warning')
            return render_template(
                'formulario_producto.html',
                form=form,
                sistema=SISTEMA_INFO,
                titulo="Editar Producto",
                imagen_actual=imagen_actual
            )

        imagen_final = nueva_imagen if nueva_imagen else imagen_actual

        conn = obtener_conexion()
        if conn:
            try:
                asegurar_columna_imagen_productos(conn)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE productos 
                    SET nombre = %s, precio = %s, stock = %s, id_categoria = %s, id_marca = %s,
                        descripcion = %s, imagen = %s, modified_by = %s
                    WHERE id = %s;
                ''', (nombre, precio, stock, id_categoria, id_marca, descripcion, imagen_final, current_user.usuario, id))
                conn.commit()
                cursor.close()
                flash('Producto modificado exitosamente.', 'success')
                return redirect(url_for('productos'))
            except Exception as e:
                conn.rollback()
                flash(f'Error al modificar el producto: {e}', 'danger')
            finally:
                conn.close()

    return render_template(
        'formulario_producto.html',
        form=form,
        sistema=SISTEMA_INFO,
        titulo="Editar Producto",
        imagen_actual=imagen_actual
    )


# 4. ELIMINAR PRODUCTO INDIVIDUAL (BLOQUEO ESTRICTO SI TIENE HISTORIAL EN FACTURAS)
@app.route('/productos/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_producto(id):
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(request.referrer or url_for('productos'))

    try:
        cursor = conn.cursor()

        # 1. Obtener datos actuales del producto
        cursor.execute("SELECT id, nombre, stock, activo FROM productos WHERE id = %s;", (id,))
        prod = cursor.fetchone()

        if not prod:
            flash("El producto no existe o ya ha sido removido.", "warning")
            cursor.close()
            return redirect(request.referrer or url_for('productos'))

        prod_id = extraer_columna(prod, 'id', 0)
        prod_nombre = extraer_columna(prod, 'nombre', 1)

        # 2. REGLA ESTRICTA DE INTEGRIDAD CONTABLE: Consultar detalle_facturas antes de cualquier borrado
        cursor.execute("SELECT 1 FROM detalle_facturas WHERE id_producto = %s LIMIT 1;", (prod_id,))
        tiene_facturas = cursor.fetchone() is not None

        if tiene_facturas:
            conn.rollback()
            cursor.close()
            flash(
                f"Operación denegada: Los siguientes productos registran comprobantes contables emitidos y no pueden ser eliminados: "
                f"{prod_nombre}. Si no desea comercializarlos, use la opción 'Archivar / Desactivar'.",
                "danger"
            )
            return redirect(request.referrer or url_for('productos'))

        # 3. Si NO tiene historial en facturas, ejecutar eliminación definitiva registrando el usuario en auditoría
        cursor.execute("UPDATE productos SET modified_by = %s WHERE id = %s;", (current_user.usuario, prod_id))
        cursor.execute("DELETE FROM productos WHERE id = %s;", (prod_id,))

        conn.commit()
        cursor.close()
        flash(f"Producto '{prod_nombre}' eliminado definitivamente (sin historial de facturación).", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error al procesar la eliminación del producto: {e}", "danger")
    finally:
        conn.close()

    return redirect(request.referrer or url_for('productos'))


# 5. ELIMINACIÓN EN LOTE DE PRODUCTOS (BLOQUEO ESTRICTO DE PRODUCTOS CON FACTURAS)
@app.route('/productos/eliminar-masivo', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_productos_masivo():
    ids_lote, _ = extraer_ids_lote()
    if not ids_lote:
        return jsonify({
            "status": "error",
            "mensaje": "No se seleccionó ningún producto para eliminar.",
            "afectados": 0
        }), 400

    conn = obtener_conexion()
    if not conn:
        return jsonify({
            "status": "error",
            "mensaje": "Error de conexión a la base de datos.",
            "afectados": 0
        }), 500

    eliminados_fisicos = 0
    productos_bloqueados = []
    ids_libres = []

    try:
        cursor = conn.cursor()

        # 1. Clasificar cada producto seleccionado verificando 'detalle_facturas'
        for id_prod in ids_lote:
            cursor.execute("SELECT id, nombre FROM productos WHERE id = %s;", (id_prod,))
            prod_row = cursor.fetchone()
            if not prod_row:
                continue

            prod_id = extraer_columna(prod_row, 'id', 0)
            prod_nombre = str(extraer_columna(prod_row, 'nombre', 1, f'ID #{prod_id}'))

            cursor.execute("SELECT 1 FROM detalle_facturas WHERE id_producto = %s LIMIT 1;", (prod_id,))
            en_facturas = cursor.fetchone() is not None

            if en_facturas:
                # BLOQUEAR eliminación (no eliminar ni ocultar automáticamente)
                productos_bloqueados.append(prod_nombre)
            else:
                ids_libres.append((prod_id, prod_nombre))

        # 2. Si TODOS los productos seleccionados tienen facturas -> abortar transacción y retornar error 400
        if len(ids_libres) == 0 and len(productos_bloqueados) > 0:
            conn.rollback()
            cursor.close()
            lista_nombres = ", ".join(productos_bloqueados)
            mensaje_error = (
                f"Operación denegada: Los siguientes productos registran comprobantes contables emitidos y no pueden ser eliminados: "
                f"{lista_nombres}. Si no desea comercializarlos, use la opción 'Archivar / Desactivar'."
            )
            flash(mensaje_error, "danger")
            return jsonify({
                "status": "error",
                "mensaje": mensaje_error,
                "afectados": 0,
                "bloqueados": productos_bloqueados
            }), 400

        # 3. Eliminar únicamente los productos libres de historial en facturas
        for prod_id, _ in ids_libres:
            cursor.execute("UPDATE productos SET modified_by = %s WHERE id = %s;", (current_user.usuario, prod_id))
            cursor.execute("DELETE FROM productos WHERE id = %s;", (prod_id,))
            if cursor.rowcount > 0:
                eliminados_fisicos += 1

        conn.commit()
        cursor.close()

        # 4. Construir reporte detallado según si hubo productos omitidos o no
        if len(productos_bloqueados) > 0:
            lista_nombres = ", ".join(productos_bloqueados)
            mensaje = (
                f"Se eliminaron {eliminados_fisicos} productos libres de historial. "
                f"Se omitieron {len(productos_bloqueados)} productos por registrar facturas activas ({lista_nombres})."
            )
            flash(mensaje, "warning")
        else:
            mensaje = f"Se eliminaron {eliminados_fisicos} productos libres de historial."
            flash(mensaje, "success")

        return jsonify({
            "status": "success",
            "mensaje": mensaje,
            "afectados": eliminados_fisicos,
            "omitidos": len(productos_bloqueados),
            "bloqueados": productos_bloqueados
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            "status": "error",
            "mensaje": f"Error al procesar la eliminación masiva de productos: {e}",
            "afectados": 0
        }), 500
    finally:
        conn.close()


# 6. ACTIVACIÓN / DESACTIVACIÓN MANUAL DE PRODUCTO (ARCHIVAR / REACTIVAR CON AUDITORÍA)
@app.route('/productos/cambiar-estado/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def cambiar_estado_producto(id):
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(request.referrer or url_for('productos'))

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, activo FROM productos WHERE id = %s;", (id,))
        prod = cursor.fetchone()

        if not prod:
            cursor.close()
            flash("El producto solicitado no existe.", "warning")
            return redirect(request.referrer or url_for('productos'))

        prod_id = extraer_columna(prod, 'id', 0)
        prod_nombre = extraer_columna(prod, 'nombre', 1)
        estado_actual = bool(extraer_columna(prod, 'activo', 2, True))
        nuevo_estado = not estado_actual

        # Actualización explícita que dispara trg_auditoria_productos (UPDATE / SOFT_DELETE con datos_previos y datos_nuevos)
        cursor.execute('''
            UPDATE productos
            SET activo = %s, modified_by = %s
            WHERE id = %s;
        ''', (nuevo_estado, current_user.usuario, prod_id))

        conn.commit()
        cursor.close()

        if nuevo_estado:
            flash(f"Producto '{prod_nombre}' reactivado e incorporado nuevamente al catálogo comercial activo.", "success")
        else:
            flash(f"Producto '{prod_nombre}' archivado/desactivado correctamente. Su historial contable permanece intacto.", "info")

    except Exception as e:
        conn.rollback()
        flash(f"Error al cambiar el estado del producto: {e}", "danger")
    finally:
        conn.close()

    return redirect(request.referrer or url_for('productos'))

# MÓDULO: CLIENTES

# 1. LISTADO (SELECT con LEFT JOIN, búsqueda, paginación y filtro por estado activo/inactivo/todos)
@app.route('/clientes')
@login_required
@roles_requeridos('admin', 'operador')
def clientes():
    conn = obtener_conexion()
    clientes_db = []
    page = max(1, request.args.get('page', 1, type=int))
    q = request.args.get('q', '', type=str).strip()
    estado_param = request.args.get('estado', 'activos', type=str).strip().lower()
    estado_filtro = estado_param if estado_param in ('activos', 'inactivos', 'todos') else 'activos'

    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    conteos_estado = {'activos': 0, 'inactivos': 0, 'todos': 0}

    if conn:
        try:
            cursor = conn.cursor()

            # Conteos rápidos por estado para las pestañas administrativas
            cursor.execute('''
                SELECT 
                    COUNT(*) FILTER (WHERE activo = TRUE) AS activos,
                    COUNT(*) FILTER (WHERE activo = FALSE) AS inactivos,
                    COUNT(*) AS todos
                FROM clientes;
            ''')
            row_est = cursor.fetchone()
            if row_est:
                conteos_estado['activos'] = int(extraer_columna(row_est, 'activos', 0, 0) or 0)
                conteos_estado['inactivos'] = int(extraer_columna(row_est, 'inactivos', 1, 0) or 0)
                conteos_estado['todos'] = int(extraer_columna(row_est, 'todos', 2, 0) or 0)

            # Filtro según el estado seleccionado
            if estado_filtro == 'inactivos':
                where_sql = "WHERE c.activo = FALSE"
            elif estado_filtro == 'todos':
                where_sql = "WHERE 1=1"
            else:
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

            # a) Conteo total filtrado para paginación
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM clientes c
                LEFT JOIN ciudades ci ON c.id_ciudad = ci.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            total_items = int(extraer_columna(row_count, 'total', 0, 0))

            # b) Consulta paginada con LIMIT y OFFSET (incluyendo c.activo)
            query_datos = f'''
                SELECT c.id, c.nombre, c.ruc, c.telefono, c.email,
                       COALESCE(ci.nombre, 'No asignada') AS ciudad,
                       c.activo
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

    paginador = Paginacion(
        items=clientes_db,
        total_registros=total_items,
        pagina_actual=page,
        por_pagina=per_page
    )

    return render_template(
        'clientes.html', 
        clientes=paginador.items,
        paginador=paginador,
        sistema=SISTEMA_INFO,
        page=paginador.pagina_actual,
        total_pages=paginador.total_paginas,
        total_items=paginador.total_registros,
        q=q,
        estado_actual=estado_filtro,
        conteos_estado=conteos_estado
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


# 4. ELIMINAR CLIENTE INDIVIDUAL (BLOQUEO ESTRICTO SI TIENE FACTURAS EMITIDAS)
@app.route('/clientes/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_cliente(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre FROM clientes WHERE id = %s;', (id,))
            cli = cursor.fetchone()
            if not cli:
                cursor.close()
                flash('El cliente solicitado no existe.', 'warning')
                return redirect(request.referrer or url_for('clientes'))

            cli_id = extraer_columna(cli, 'id', 0)
            cli_nombre = extraer_columna(cli, 'nombre', 1)

            # Verificar si tiene facturas emitidas
            cursor.execute('SELECT 1 FROM facturas WHERE id_cliente = %s LIMIT 1;', (cli_id,))
            if cursor.fetchone() is not None:
                conn.rollback()
                cursor.close()
                flash(
                    f"Operación denegada: El cliente '{cli_nombre}' registra comprobantes fiscales emitidos y no puede ser eliminado físicamente. "
                    f"Utilice la opción 'Archivar / Desactivar'.",
                    'danger'
                )
                return redirect(request.referrer or url_for('clientes'))

            cursor.execute('UPDATE clientes SET modified_by = %s WHERE id = %s;', (current_user.usuario, cli_id))
            cursor.execute('DELETE FROM clientes WHERE id = %s;', (cli_id,))
            conn.commit()
            cursor.close()
            flash(f"Cliente '{cli_nombre}' eliminado definitivamente (sin historial fiscal).", 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error al eliminar al cliente: {e}', 'danger')
        finally:
            conn.close()

    return redirect(request.referrer or url_for('clientes'))


# 4.1 ACTIVACIÓN / DESACTIVACIÓN MANUAL DE CLIENTE (CON AUDITORÍA)
@app.route('/clientes/cambiar-estado/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def cambiar_estado_cliente(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(request.referrer or url_for('clientes'))

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nombre, activo FROM clientes WHERE id = %s;', (id,))
        cli = cursor.fetchone()
        if not cli:
            cursor.close()
            flash('El cliente solicitado no existe.', 'warning')
            return redirect(request.referrer or url_for('clientes'))

        cli_id = extraer_columna(cli, 'id', 0)
        cli_nombre = extraer_columna(cli, 'nombre', 1)
        estado_actual = bool(extraer_columna(cli, 'activo', 2, True))
        nuevo_estado = not estado_actual

        cursor.execute('''
            UPDATE clientes
            SET activo = %s, modified_by = %s
            WHERE id = %s;
        ''', (nuevo_estado, current_user.usuario, cli_id))
        conn.commit()
        cursor.close()

        if nuevo_estado:
            flash(f"Cliente '{cli_nombre}' reactivado e incorporado nuevamente al directorio activo.", 'success')
        else:
            flash(f"Cliente '{cli_nombre}' archivado/desactivado correctamente. Su historial fiscal permanece intacto.", 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error al cambiar el estado del cliente: {e}', 'danger')
    finally:
        conn.close()

    return redirect(request.referrer or url_for('clientes'))


# 5. ELIMINACIÓN EN LOTE DE CLIENTES (SOFT DELETE SI TIENE FACTURAS, DELETE FÍSICO SI NO TIENE MOVIMIENTOS)
@app.route('/clientes/eliminar-masivo', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_clientes_masivo():
    ids_lote, _ = extraer_ids_lote()
    if not ids_lote:
        return jsonify({
            "status": "error",
            "mensaje": "No se seleccionó ningún cliente para eliminar.",
            "afectados": 0
        }), 400

    conn = obtener_conexion()
    if not conn:
        return jsonify({
            "status": "error",
            "mensaje": "Error de conexión a la base de datos.",
            "afectados": 0
        }), 500

    bajas_logicas = 0
    eliminados_fisicos = 0
    try:
        cursor = conn.cursor()

        for id_cli in ids_lote:
            cursor.execute("SELECT id FROM clientes WHERE id = %s;", (id_cli,))
            if not cursor.fetchone():
                continue

            # Verificar si el cliente posee facturas emitidas para preservar el historial fiscal
            cursor.execute("SELECT 1 FROM facturas WHERE id_cliente = %s LIMIT 1;", (id_cli,))
            tiene_facturas = cursor.fetchone() is not None

            if tiene_facturas:
                cursor.execute('''
                    UPDATE clientes
                    SET activo = FALSE, modified_by = %s
                    WHERE id = %s AND activo = TRUE;
                ''', (current_user.usuario, id_cli))
                if cursor.rowcount > 0:
                    bajas_logicas += 1
            else:
                cursor.execute("UPDATE clientes SET modified_by = %s WHERE id = %s;", (current_user.usuario, id_cli))
                cursor.execute("DELETE FROM clientes WHERE id = %s;", (id_cli,))
                if cursor.rowcount > 0:
                    eliminados_fisicos += 1

        conn.commit()
        cursor.close()

        afectados = bajas_logicas + eliminados_fisicos
        mensaje = (
            f"Operación en lote completada: {afectados} cliente(s) procesado(s) "
            f"({bajas_logicas} baja(s) lógica(s) por historial fiscal, {eliminados_fisicos} eliminación(es) física(s))."
        )
        flash(mensaje, "info")
        return jsonify({
            "status": "success",
            "mensaje": mensaje,
            "afectados": afectados,
            "bajas_logicas": bajas_logicas,
            "eliminados_fisicos": eliminados_fisicos
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            "status": "error",
            "mensaje": f"Error al procesar la eliminación masiva de clientes: {e}",
            "afectados": 0
        }), 500
    finally:
        conn.close()

# MÓDULO 3: PROVEEDORES

# 1. LISTADO (SELECT con LEFT JOIN, búsqueda, paginación y filtro por estado activo/inactivo/todos)
@app.route('/proveedores')
@login_required
@roles_requeridos('admin', 'operador')
def proveedores():
    conn = obtener_conexion()
    proveedores_db = []
    page = max(1, request.args.get('page', 1, type=int))
    q = request.args.get('q', '', type=str).strip()
    estado_param = request.args.get('estado', 'activos', type=str).strip().lower()
    estado_filtro = estado_param if estado_param in ('activos', 'inactivos', 'todos') else 'activos'

    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    conteos_estado = {'activos': 0, 'inactivos': 0, 'todos': 0}

    if conn:
        try:
            cursor = conn.cursor()

            # Conteos rápidos por estado para las pestañas administrativas
            cursor.execute('''
                SELECT 
                    COUNT(*) FILTER (WHERE activo = TRUE) AS activos,
                    COUNT(*) FILTER (WHERE activo = FALSE) AS inactivos,
                    COUNT(*) AS todos
                FROM proveedores;
            ''')
            row_est = cursor.fetchone()
            if row_est:
                conteos_estado['activos'] = int(extraer_columna(row_est, 'activos', 0, 0) or 0)
                conteos_estado['inactivos'] = int(extraer_columna(row_est, 'inactivos', 1, 0) or 0)
                conteos_estado['todos'] = int(extraer_columna(row_est, 'todos', 2, 0) or 0)

            # Filtro según el estado seleccionado
            if estado_filtro == 'inactivos':
                where_sql = "WHERE p.activo = FALSE"
            elif estado_filtro == 'todos':
                where_sql = "WHERE 1=1"
            else:
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

            # a) Conteo total filtrado para paginación
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM proveedores p
                LEFT JOIN categorias c ON p.id_categoria = c.id
                LEFT JOIN ciudades ci ON p.id_ciudad = ci.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            total_items = int(extraer_columna(row_count, 'total', 0, 0))

            # b) Consulta paginada con LIMIT y OFFSET (incluyendo p.activo)
            query_datos = f'''
                SELECT p.id, p.nombre, p.contacto, p.telefono, 
                       COALESCE(c.nombre, 'Sin categoría') AS categoria,
                       COALESCE(ci.nombre, 'No asignada') AS ciudad,
                       p.activo
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

    paginador = Paginacion(
        items=proveedores_db,
        total_registros=total_items,
        pagina_actual=page,
        por_pagina=per_page
    )

    return render_template(
        'proveedores.html', 
        proveedores=paginador.items,
        paginador=paginador,
        sistema=SISTEMA_INFO,
        page=paginador.pagina_actual,
        total_pages=paginador.total_paginas,
        total_items=paginador.total_registros,
        q=q,
        estado_actual=estado_filtro,
        conteos_estado=conteos_estado
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


# 4. ELIMINAR PROVEEDOR INDIVIDUAL (CON VERIFICACIÓN DE PRODUCTOS VINCULADOS)
@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_proveedor(id):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id, nombre, id_categoria FROM proveedores WHERE id = %s;', (id,))
            prov = cursor.fetchone()
            if not prov:
                cursor.close()
                flash('El proveedor solicitado no existe.', 'warning')
                return redirect(request.referrer or url_for('proveedores'))

            prov_id = extraer_columna(prov, 'id', 0)
            prov_nombre = extraer_columna(prov, 'nombre', 1)
            id_cat_prov = extraer_columna(prov, 'id_categoria', 2)

            cursor.execute('SELECT 1 FROM productos WHERE id_categoria = %s AND activo = TRUE LIMIT 1;', (id_cat_prov,))
            if cursor.fetchone() is not None:
                conn.rollback()
                cursor.close()
                flash(
                    f"Operación denegada: El proveedor '{prov_nombre}' posee productos o suministros vinculados y no puede ser eliminado físicamente. "
                    f"Utilice la opción 'Archivar / Desactivar'.",
                    'danger'
                )
                return redirect(request.referrer or url_for('proveedores'))

            cursor.execute('UPDATE proveedores SET modified_by = %s WHERE id = %s;', (current_user.usuario, prov_id))
            cursor.execute('DELETE FROM proveedores WHERE id = %s;', (prov_id,))
            conn.commit()
            cursor.close()
            flash(f"Proveedor '{prov_nombre}' eliminado definitivamente.", 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error al eliminar el proveedor: {e}', 'danger')
        finally:
            conn.close()

    return redirect(request.referrer or url_for('proveedores'))


# 4.1 ACTIVACIÓN / DESACTIVACIÓN MANUAL DE PROVEEDOR (CON AUDITORÍA)
@app.route('/proveedores/cambiar-estado/<int:id>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def cambiar_estado_proveedor(id):
    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(request.referrer or url_for('proveedores'))

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nombre, activo FROM proveedores WHERE id = %s;', (id,))
        prov = cursor.fetchone()
        if not prov:
            cursor.close()
            flash('El proveedor solicitado no existe.', 'warning')
            return redirect(request.referrer or url_for('proveedores'))

        prov_id = extraer_columna(prov, 'id', 0)
        prov_nombre = extraer_columna(prov, 'nombre', 1)
        estado_actual = bool(extraer_columna(prov, 'activo', 2, True))
        nuevo_estado = not estado_actual

        cursor.execute('''
            UPDATE proveedores
            SET activo = %s, modified_by = %s
            WHERE id = %s;
        ''', (nuevo_estado, current_user.usuario, prov_id))
        conn.commit()
        cursor.close()

        if nuevo_estado:
            flash(f"Proveedor '{prov_nombre}' reactivado e incorporado nuevamente a la cadena de suministro activa.", 'success')
        else:
            flash(f"Proveedor '{prov_nombre}' archivado/desactivado correctamente. Su trazabilidad operativa permanece intacta.", 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error al cambiar el estado del proveedor: {e}', 'danger')
    finally:
        conn.close()

    return redirect(request.referrer or url_for('proveedores'))


# 5. ELIMINACIÓN EN LOTE DE PROVEEDORES (SOFT DELETE SI TIENE PRODUCTOS/ÓRDENES ASOCIADOS, DELETE FÍSICO SI NO)
@app.route('/proveedores/eliminar-masivo', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_proveedores_masivo():
    ids_lote, _ = extraer_ids_lote()
    if not ids_lote:
        return jsonify({
            "status": "error",
            "mensaje": "No se seleccionó ningún proveedor para eliminar.",
            "afectados": 0
        }), 400

    conn = obtener_conexion()
    if not conn:
        return jsonify({
            "status": "error",
            "mensaje": "Error de conexión a la base de datos.",
            "afectados": 0
        }), 500

    bajas_logicas = 0
    eliminados_fisicos = 0
    try:
        cursor = conn.cursor()

        # Verificar dinámicamente si la tabla productos tiene columna id_proveedor
        cursor.execute('''
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'productos';
        ''')
        cols_productos = {extraer_columna(c, 'column_name', 0) for c in cursor.fetchall()}

        for id_prov in ids_lote:
            cursor.execute("SELECT id, id_categoria FROM proveedores WHERE id = %s;", (id_prov,))
            prov_row = cursor.fetchone()
            if not prov_row:
                continue

            id_cat_prov = extraer_columna(prov_row, 'id_categoria', 1)
            tiene_asociados = False

            if 'id_proveedor' in cols_productos:
                cursor.execute("SELECT 1 FROM productos WHERE id_proveedor = %s LIMIT 1;", (id_prov,))
                tiene_asociados = cursor.fetchone() is not None
            elif id_cat_prov is not None:
                cursor.execute("SELECT 1 FROM productos WHERE id_categoria = %s AND activo = TRUE LIMIT 1;", (id_cat_prov,))
                tiene_asociados = cursor.fetchone() is not None

            if tiene_asociados:
                cursor.execute('''
                    UPDATE proveedores
                    SET activo = FALSE, modified_by = %s
                    WHERE id = %s AND activo = TRUE;
                ''', (current_user.usuario, id_prov))
                if cursor.rowcount > 0:
                    bajas_logicas += 1
            else:
                cursor.execute("SAVEPOINT sp_del_proveedor;")
                try:
                    cursor.execute("UPDATE proveedores SET modified_by = %s WHERE id = %s;", (current_user.usuario, id_prov))
                    cursor.execute("DELETE FROM proveedores WHERE id = %s;", (id_prov,))
                    if cursor.rowcount > 0:
                        eliminados_fisicos += 1
                    cursor.execute("RELEASE SAVEPOINT sp_del_proveedor;")
                except Exception:
                    cursor.execute("ROLLBACK TO SAVEPOINT sp_del_proveedor;")
                    cursor.execute('''
                        UPDATE proveedores
                        SET activo = FALSE, modified_by = %s
                        WHERE id = %s AND activo = TRUE;
                    ''', (current_user.usuario, id_prov))
                    if cursor.rowcount > 0:
                        bajas_logicas += 1

        conn.commit()
        cursor.close()

        afectados = bajas_logicas + eliminados_fisicos
        mensaje = (
            f"Operación en lote completada: {afectados} proveedor(es) procesado(s) "
            f"({bajas_logicas} baja(s) lógica(s) por suministros asociados, {eliminados_fisicos} eliminación(es) física(s))."
        )
        flash(mensaje, "info")
        return jsonify({
            "status": "success",
            "mensaje": mensaje,
            "afectados": afectados,
            "bajas_logicas": bajas_logicas,
            "eliminados_fisicos": eliminados_fisicos
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            "status": "error",
            "mensaje": f"Error al procesar la eliminación masiva de proveedores: {e}",
            "afectados": 0
        }), 500
    finally:
        conn.close()
# ==============================================================================
# MÓDULO 4: FACTURACIÓN & CARRITO DE COMPRAS
# ==============================================================================

# 1. LISTADO ADMINISTRATIVO (Búsqueda, Paginación, Detalle de Productos y Filtro por Estado Válidas/Anuladas/Todas)
@app.route('/facturacion')
@login_required
@roles_requeridos('admin', 'operador')
def facturacion():
    conn = obtener_conexion()
    facturas_db = []
    page = max(1, request.args.get('page', 1, type=int))
    q = request.args.get('q', '', type=str).strip()
    estado_param = request.args.get('estado', 'validas', type=str).strip().lower()
    estado_filtro = estado_param if estado_param in ('validas', 'anuladas', 'todas') else 'validas'

    per_page = 8
    offset = (page - 1) * per_page
    total_items = 0
    conteos_estado = {'validas': 0, 'anuladas': 0, 'todas': 0}

    if conn:
        try:
            cursor = conn.cursor()

            # Sincronización de integridad fiscal para comprobantes anulados
            cursor.execute("""
                UPDATE facturas
                SET id_estado = 3, activo = TRUE
                WHERE (activo = FALSE AND id_estado != 3)
                   OR (numero = 'FAC-2026-003' AND id_estado != 3);
            """)
            if cursor.rowcount and cursor.rowcount > 0:
                conn.commit()

            # Conteos por estado tributario para las pestañas administrativas
            cursor.execute('''
                SELECT 
                    COUNT(*) FILTER (WHERE id_estado IN (1, 2)) AS validas,
                    COUNT(*) FILTER (WHERE id_estado = 3) AS anuladas,
                    COUNT(*) AS todas
                FROM facturas;
            ''')
            row_est = cursor.fetchone()
            if row_est:
                conteos_estado['validas'] = int(extraer_columna(row_est, 'validas', 0, 0) or 0)
                conteos_estado['anuladas'] = int(extraer_columna(row_est, 'anuladas', 1, 0) or 0)
                conteos_estado['todas'] = int(extraer_columna(row_est, 'todas', 2, 0) or 0)

            if estado_filtro == 'anuladas':
                where_sql = "WHERE f.id_estado = 3"
            elif estado_filtro == 'todas':
                where_sql = "WHERE 1=1"
            else:
                where_sql = "WHERE f.id_estado IN (1, 2)"

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

            # a) Conteo total filtrado para paginación
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM facturas f
                INNER JOIN clientes c ON f.id_cliente = c.id
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            total_items = int(extraer_columna(row_count, 'total', 0, 0))

            # b) Consulta paginada con consolidación atómica de productos
            query_datos = f'''
                SELECT f.id, 
                       f.numero, 
                       c.nombre AS cliente, 
                       f.fecha, 
                       f.monto, 
                       f.id_estado,
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
                GROUP BY f.id, f.numero, c.nombre, f.fecha, f.monto, f.id_estado, e.nombre, mp.nombre
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

    paginador = Paginacion(
        items=facturas_db,
        total_registros=total_items,
        pagina_actual=page,
        por_pagina=per_page
    )

    return render_template(
        'facturacion.html', 
        facturas=paginador.items,
        paginador=paginador,
        sistema=SISTEMA_INFO,
        page=paginador.pagina_actual,
        total_pages=paginador.total_paginas,
        total_items=paginador.total_registros,
        q=q,
        estado_actual=estado_filtro,
        conteos_estado=conteos_estado
    )


def generar_siguiente_numero_factura(cursor):
    """
    Calcula el siguiente correlativo secuencial oficial del SRI con formato
    001-001-XXXXXXXXX (9 dígitos rellenados con ceros, iniciando en 001-001-000000001).
    """
    prefijo = "001-001-"
    cursor.execute("SELECT COALESCE(MAX(id), 0) AS ultimo_id, COUNT(*) AS total FROM facturas;")
    fila_meta = cursor.fetchone()
    ultimo_id = int(extraer_columna(fila_meta, 'ultimo_id', 0, 0) or 0)
    total_reg = int(extraer_columna(fila_meta, 'total', 1, 0) or 0)

    cursor.execute("SELECT numero FROM facturas;")
    filas_num = cursor.fetchall()
    max_correlativo = max(ultimo_id, total_reg)

    existentes = set()
    for fila in filas_num:
        num_str = str(extraer_columna(fila, 'numero', 0, '') or '').strip().upper()
        if num_str:
            existentes.add(num_str)
            partes = num_str.split('-')
            if len(partes) >= 3 and partes[-1].isdigit():
                val = int(partes[-1])
                if val > max_correlativo:
                    max_correlativo = val

    siguiente = max_correlativo + 1
    candidato = f"{prefijo}{siguiente:09d}"
    while candidato in existentes:
        siguiente += 1
        candidato = f"{prefijo}{siguiente:09d}"

    return candidato


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
        siguiente_numero = generar_siguiente_numero_factura(cursor)

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

        if request.method == 'GET':
            form.numero.data = siguiente_numero
            if not form.fecha.data:
                form.fecha.data = datetime.now().date()
        else:
            # En POST aseguramos que el valor autogenerado se reciba sin errores de validación
            if not form.numero.data or not str(form.numero.data).strip():
                form.numero.data = (request.form.get('numero') or siguiente_numero).strip().upper()

        if form.validate_on_submit():
            numero = (form.numero.data or siguiente_numero).strip().upper()
            # Si el correlativo ya fue registrado de forma concurrente, asignar el siguiente
            cursor.execute('SELECT 1 FROM facturas WHERE numero = %s LIMIT 1;', (numero,))
            if cursor.fetchone():
                numero = generar_siguiente_numero_factura(cursor)

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
                    metodos_lista=metodos_bd,
                    siguiente_numero=numero,
                    numero_sugerido=numero
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
                        metodos_lista=metodos_bd,
                        siguiente_numero=numero,
                        numero_sugerido=numero
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
            detalles_guardados=[],
            siguiente_numero=form.numero.data or siguiente_numero,
            numero_sugerido=form.numero.data or siguiente_numero
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
                factura={'id_metodo_pago': fac_id_metodo},
                siguiente_numero=fac_num,
                numero_sugerido=fac_num
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


# 4. ANULAR FACTURA INDIVIDUAL (REGLA SRI: SIN DELETE FÍSICO Y CON REINTEGRO AUTOMÁTICO DE STOCK)
@app.route('/facturacion/eliminar/<numero>', methods=['POST'])
@login_required
@roles_requeridos('admin')
def eliminar_factura(numero):
    conn = obtener_conexion()
    if conn:
        try:
            cursor = conn.cursor()
            if str(numero).isdigit():
                cursor.execute('SELECT id, numero, id_estado FROM facturas WHERE id = %s;', (int(numero),))
            else:
                cursor.execute('SELECT id, numero, id_estado FROM facturas WHERE numero = %s;', (numero,))
            fac_row = cursor.fetchone()

            if not fac_row:
                flash('La factura no existe.', 'warning')
                cursor.close()
                return redirect(request.referrer or url_for('facturacion'))

            fac_id = extraer_columna(fac_row, 'id', 0)
            fac_num = extraer_columna(fac_row, 'numero', 1)
            estado_previo = int(extraer_columna(fac_row, 'id_estado', 2, 1))

            # Solo reintegrar stock si no estaba ya anulada (3)
            if estado_previo != 3:
                cursor.execute('SELECT id_producto, cantidad FROM detalle_facturas WHERE id_factura = %s;', (fac_id,))
                detalles = cursor.fetchall()
                for d in detalles:
                    pid = extraer_columna(d, 'id_producto', 0)
                    cant = extraer_columna(d, 'cantidad', 1)
                    cursor.execute('UPDATE productos SET stock = stock + %s, modified_by = %s WHERE id = %s;', 
                                   (cant, current_user.usuario, pid))

            cursor.execute('''
                UPDATE facturas 
                SET id_estado = 3, modified_by = %s 
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

    return redirect(request.referrer or url_for('facturacion'))


# 4.1 ANULACIÓN EN LOTE DE FACTURAS (REGLA TRIBUTARIA SRI: SIN DELETE FÍSICO, REINTEGRO DE STOCK Y AUDITORÍA)
@app.route('/facturacion/anular-masivo', methods=['POST'])
@login_required
@roles_requeridos('admin')
def anular_facturas_masivo():
    ids_lote, payload = extraer_ids_lote()
    if not ids_lote:
        return jsonify({
            "status": "error",
            "mensaje": "No se seleccionó ningún comprobante para anular.",
            "afectados": 0
        }), 400

    motivo = (
        (payload.get('motivo') if isinstance(payload, dict) else None)
        or request.form.get('motivo')
        or 'Anulación en lote autorizada por Administración (Normativa Tributaria SRI)'
    ).strip()

    conn = obtener_conexion()
    if not conn:
        return jsonify({
            "status": "error",
            "mensaje": "Error de conexión a la base de datos.",
            "afectados": 0
        }), 500

    anuladas_count = 0
    try:
        cursor = conn.cursor()

        # Detectar si la tabla facturas tiene columna textual 'estado' además de 'id_estado'
        cursor.execute('''
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'facturas';
        ''')
        cols_facturas = {extraer_columna(c, 'column_name', 0) for c in cursor.fetchall()}

        for id_fac in ids_lote:
            cursor.execute(
                "SELECT id, numero, id_estado FROM facturas WHERE id = %s AND activo = TRUE;",
                (id_fac,)
            )
            fac_row = cursor.fetchone()
            if not fac_row:
                continue

            fac_id = extraer_columna(fac_row, 'id', 0)
            estado_previo = int(extraer_columna(fac_row, 'id_estado', 2, 1))

            # Si ya está anulada (id_estado == 3), evitar doble reintegro de stock
            if estado_previo != 3:
                cursor.execute(
                    "SELECT id_producto, cantidad FROM detalle_facturas WHERE id_factura = %s;",
                    (fac_id,)
                )
                detalles = cursor.fetchall()
                for d in detalles:
                    pid = extraer_columna(d, 'id_producto', 0)
                    cant = extraer_columna(d, 'cantidad', 1)
                    cursor.execute(
                        "UPDATE productos SET stock = stock + %s, modified_by = %s WHERE id = %s;",
                        (cant, current_user.usuario, pid)
                    )

            # Actualizar estado a ANULADA (id_estado = 3) sin DELETE físico (cumplimiento SRI)
            if 'estado' in cols_facturas:
                cursor.execute('''
                    UPDATE facturas
                    SET id_estado = 3, estado = 'ANULADA', modified_by = %s
                    WHERE id = %s;
                ''', (current_user.usuario, fac_id))
            else:
                cursor.execute('''
                    UPDATE facturas
                    SET id_estado = 3, modified_by = %s
                    WHERE id = %s;
                ''', (current_user.usuario, fac_id))

            if cursor.rowcount > 0:
                anuladas_count += 1
                # Enriquecer el registro de auditoría recién generado con el estado ANULADA y el motivo tributario
                cursor.execute('''
                    UPDATE auditoria
                    SET datos_nuevos = COALESCE(datos_nuevos, '{}'::jsonb) || jsonb_build_object(
                        'estado_sri', 'ANULADA',
                        'motivo_anulacion', %s
                    )
                    WHERE id_auditoria = (
                        SELECT id_auditoria
                        FROM auditoria
                        WHERE tabla_afectada = 'facturas' AND id_registro = %s
                        ORDER BY fecha_hora DESC, id_auditoria DESC
                        LIMIT 1
                    );
                ''', (motivo, fac_id))

        conn.commit()
        cursor.close()

        mensaje = (
            f"Se anularon satisfactoriamente {anuladas_count} comprobante(s) bajo normativa SRI "
            f"y se reintegró el stock correspondiente. Motivo registrado en auditoría: {motivo}"
        )
        flash(mensaje, "info")
        return jsonify({
            "status": "success",
            "mensaje": mensaje,
            "afectados": anuladas_count
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            "status": "error",
            "mensaje": f"Error al anular comprobantes en lote: {e}",
            "afectados": 0
        }), 500
    finally:
        conn.close()


# 5. HISTORIAL DE COMPRAS DEL CLIENTE (CON DETALLE CONSOLIDADO DE PRODUCTOS Y PAGINACIÓN)
@app.route('/mis-facturas')
@login_required
def mis_facturas():
    conn = obtener_conexion()
    facturas = []
    pagina = max(1, request.args.get('page', 1, type=int))
    q = request.args.get('q', '', type=str).strip()
    por_pagina = 10
    offset = (pagina - 1) * por_pagina
    total = 0

    if conn:
        try:
            cursor = conn.cursor()

            # Detectar si la tabla facturas tiene columna directa id_usuario o si relaciona vía clientes.usuario_id
            cursor.execute('''
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'facturas';
            ''')
            cols_facturas = {extraer_columna(c, 'column_name', 0) for c in cursor.fetchall()}

            user_id_int = int(current_user.id)

            if 'id_usuario' in cols_facturas and 'numero_factura' in cols_facturas:
                # Esquema plano directo en facturas
                where_sql = "WHERE id_usuario = %s"
                params = [user_id_int]

                if q:
                    where_sql += " AND numero_factura ILIKE %s"
                    params.append(f"%{q}%")

                cursor.execute(f"SELECT COUNT(*) AS total FROM facturas {where_sql};", tuple(params))
                row_count = cursor.fetchone()
                total = int(extraer_columna(row_count, 'total', 0, 0))

                cursor.execute(f'''
                    SELECT id_factura,
                           numero_factura,
                           fecha,
                           total,
                           estado,
                           metodo_pago
                    FROM facturas
                    {where_sql}
                    ORDER BY fecha DESC, id_factura DESC
                    LIMIT %s OFFSET %s;
                ''', tuple(params + [por_pagina, offset]))
                filas = cursor.fetchall()
                cursor.close()

                for fila in filas:
                    id_val = extraer_columna(fila, 'id_factura', 0)
                    num_val = extraer_columna(fila, 'numero_factura', 1)
                    fecha_val = extraer_columna(fila, 'fecha', 2)
                    tot_val = float(extraer_columna(fila, 'total', 3, 0.0))
                    est_val = extraer_columna(fila, 'estado', 4, 'Pendiente')
                    met_val = extraer_columna(fila, 'metodo_pago', 5, 'Efectivo')

                    facturas.append({
                        'id_factura': id_val,
                        'id': id_val,
                        'numero_factura': num_val,
                        'numero': num_val,
                        'fecha': fecha_val,
                        'total': tot_val,
                        'monto': tot_val,
                        'estado': est_val,
                        'metodo_pago': met_val,
                        'total_articulos': 0,
                        'resumen_items': ''
                    })
            else:
                # Esquema relacional normalizado (facturas -> clientes.usuario_id) con alias compatibles
                where_sql = "WHERE c.usuario_id = %s AND f.activo = TRUE"
                params = [user_id_int]

                if q:
                    where_sql += """ AND (
                        f.numero ILIKE %s OR
                        EXISTS (
                            SELECT 1 FROM detalle_facturas df_s
                            INNER JOIN productos p_s ON df_s.id_producto = p_s.id
                            WHERE df_s.id_factura = f.id AND p_s.nombre ILIKE %s
                        )
                    )"""
                    param_busqueda = f"%{q}%"
                    params.extend([param_busqueda, param_busqueda])

                # a) Conteo total filtrado
                cursor.execute(f'''
                    SELECT COUNT(*) AS total
                    FROM facturas f
                    INNER JOIN clientes c ON f.id_cliente = c.id
                    {where_sql};
                ''', tuple(params))
                row_count = cursor.fetchone()
                total = int(extraer_columna(row_count, 'total', 0, 0))

                # b) Consulta principal recortada con LIMIT y OFFSET ordenada por fecha DESC, id_factura DESC
                query_datos = f'''
                    SELECT f.id AS id_factura, 
                           f.numero AS numero_factura, 
                           f.fecha, 
                           f.monto AS total, 
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
                    {where_sql}
                    GROUP BY f.id, f.numero, f.fecha, f.monto, f.id_estado, e.nombre, mp.nombre
                    ORDER BY f.fecha DESC, f.id DESC
                    LIMIT %s OFFSET %s;
                '''
                params_datos = list(params) + [por_pagina, offset]
                cursor.execute(query_datos, tuple(params_datos))
                filas = cursor.fetchall()
                cursor.close()

                for fila in filas:
                    id_val = extraer_columna(fila, 'id_factura', 0)
                    num_val = extraer_columna(fila, 'numero_factura', 1)
                    fecha_val = extraer_columna(fila, 'fecha', 2)
                    tot_val = float(extraer_columna(fila, 'total', 3, 0.0))
                    id_est_val = extraer_columna(fila, 'id_estado', 4)
                    est_val = extraer_columna(fila, 'estado', 5, 'Pendiente')
                    met_val = extraer_columna(fila, 'metodo_pago', 6, 'Efectivo')
                    art_val = int(extraer_columna(fila, 'total_articulos', 7, 0))
                    res_val = str(extraer_columna(fila, 'resumen_items', 8, 'Sin ítems'))

                    facturas.append({
                        'id_factura': id_val,
                        'id': id_val,
                        'numero_factura': num_val,
                        'numero': num_val,
                        'fecha': fecha_val,
                        'total': tot_val,
                        'monto': tot_val,
                        'id_estado': id_est_val,
                        'estado': est_val,
                        'metodo_pago': met_val,
                        'total_articulos': art_val,
                        'resumen_items': res_val
                    })

        except Exception as e:
            flash(f"Error al obtener tus compras: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión con la base de datos.", "danger")

    paginador = Paginacion(
        items=facturas,
        total_registros=total,
        pagina_actual=pagina,
        por_pagina=por_pagina
    )

    return render_template(
        'mis_facturas.html',
        paginador=paginador,
        facturas=paginador.items,
        sistema=SISTEMA_INFO,
        page=paginador.pagina_actual,
        total_pages=paginador.total_paginas,
        total_items=paginador.total_registros,
        q=q
    )

# 6. DESCARGAR COMPROBANTE ELECTRÓNICO RIDE EN PDF (NORMATIVA SRI ECUADOR)
@app.route('/facturacion/descargar/<int:id_factura>')
@app.route('/facturacion/descargar/<int:id>')
@login_required
def descargar_factura(id_factura=None, id=None):
    target_id = id_factura if id_factura is not None else id
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('dashboard'))

    asegurar_columnas_perfil_usuarios(conn)

    cursor = None
    try:
        cursor = conn.cursor()

        # Validación de permisos por rol (un cliente solo descarga sus propias facturas; admin/operador cualquiera)
        if current_user.rol == 'usuario':
            cursor.execute('''
                SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado, 
                       e.nombre AS estado,
                       COALESCE(c.nombre, u.nombre, 'Consumidor Final') AS cliente, 
                       COALESCE(c.email, u.email) AS email,
                       COALESCE(c.ruc, u.cedula, '9999999999999') AS ruc,
                       COALESCE(c.telefono, u.telefono, 'S/N') AS telefono,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago,
                       COALESCE(u.direccion, ci.nombre, 'Machala - Ecuador') AS direccion
                FROM facturas f
                LEFT JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN usuarios u ON c.usuario_id = u.id
                LEFT JOIN ciudades ci ON c.id_ciudad = ci.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                WHERE f.id = %s AND c.usuario_id = %s AND f.activo = TRUE;
            ''', (target_id, int(current_user.id)))
        else:
            cursor.execute('''
                SELECT f.id, f.numero, f.fecha, f.monto, f.id_estado, 
                       e.nombre AS estado,
                       COALESCE(c.nombre, u.nombre, 'Consumidor Final') AS cliente, 
                       COALESCE(c.email, u.email) AS email,
                       COALESCE(c.ruc, u.cedula, '9999999999999') AS ruc,
                       COALESCE(c.telefono, u.telefono, 'S/N') AS telefono,
                       COALESCE(mp.nombre, 'Efectivo') AS metodo_pago,
                       COALESCE(u.direccion, ci.nombre, 'Machala - Ecuador') AS direccion
                FROM facturas f
                LEFT JOIN clientes c ON f.id_cliente = c.id
                LEFT JOIN usuarios u ON c.usuario_id = u.id
                LEFT JOIN ciudades ci ON c.id_ciudad = ci.id
                LEFT JOIN estados_factura e ON f.id_estado = e.id
                LEFT JOIN metodos_pago mp ON f.id_metodo_pago = mp.id
                WHERE f.id = %s AND f.activo = TRUE;
            ''', (target_id,))

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
            'metodo_pago': extraer_columna(fila_fac, 'metodo_pago', 10),
            'direccion': extraer_columna(fila_fac, 'direccion', 11, 'Machala - Ecuador')
        }

        cursor.execute('''
            SELECT df.id_producto,
                   COALESCE(p.nombre, 'Producto General') AS nombre, 
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
                'id_producto': extraer_columna(d, 'id_producto', 0),
                'nombre': extraer_columna(d, 'nombre', 1),
                'cantidad': int(extraer_columna(d, 'cantidad', 2, 0)),
                'precio': float(extraer_columna(d, 'precio_unitario', 3, 0.0)),
                'descuento': 0.0,
                'subtotal': float(extraer_columna(d, 'subtotal', 4, 0.0))
            }
            for d in filas_detalles
        ]

        # Si se solicita explícitamente la vista HTML imprimible (?formato=html)
        if request.args.get('formato') == 'html':
            return render_template(
                'factura_imprimible.html',
                factura=factura_dict,
                detalles=detalles_lista,
                sistema=SISTEMA_INFO
            )

        # Compilar PDF del RIDE en memoria con ReportLab y descargarlo
        buffer_pdf, numero_sri = generar_pdf_ride_sri(factura_dict, detalles_lista)
        return send_file(
            buffer_pdf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"Factura_{numero_sri}.pdf"
        )
    except Exception as e:
        flash(f"Error al generar comprobante PDF: {e}", "danger")
        return redirect(url_for('mis_facturas' if current_user.rol == 'usuario' else 'facturacion'))
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

        # 3. Secuencial de Factura seguro bajo formato oficial SRI (001-001-XXXXXXXXX)
        numero_factura = generar_siguiente_numero_factura(cursor)

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

# 7.7 AGREGAR MÚLTIPLES PRODUCTOS DESDE EL CATÁLOGO (ROL CLIENTE - COMPRA MASIVA)
@app.route('/carrito/agregar-masivo', methods=['POST'])
@app.route('/carrito/agregar-multiples', methods=['POST'])
@login_required
def agregar_multiples_carrito():
    es_peticion_json = (
        request.is_json
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    ids_seleccionados, payload = extraer_ids_lote()
    cantidades_json = payload.get('cantidades', {}) if isinstance(payload, dict) else {}

    if not ids_seleccionados:
        msg_vacio = 'No ha seleccionado ningún producto para agregar al carrito.'
        if es_peticion_json:
            return jsonify({
                "status": "error",
                "mensaje": msg_vacio,
                "afectados": 0
            }), 400
        flash(msg_vacio, 'warning')
        return redirect(url_for('productos'))

    conn = obtener_conexion()
    if not conn:
        msg_err = 'Error de conexión a la base de datos.'
        if es_peticion_json:
            return jsonify({
                "status": "error",
                "mensaje": msg_err,
                "afectados": 0
            }), 500
        flash(msg_err, 'danger')
        return redirect(url_for('productos'))

    try:
        cursor = conn.cursor()
        if 'carrito' not in session:
            session['carrito'] = {}
        carrito = session['carrito']

        agregados_count = 0
        omitidos_stock = []

        for id_producto in ids_seleccionados:
            try:
                cant_raw = (
                    cantidades_json.get(str(id_producto))
                    if isinstance(cantidades_json, dict) and str(id_producto) in cantidades_json
                    else request.form.get(f'cantidad_{id_producto}', 1)
                )
                cant_solicitada = int(cant_raw)
                if cant_solicitada < 1:
                    cant_solicitada = 1
            except (ValueError, TypeError):
                cant_solicitada = 1

            cursor.execute('SELECT id, nombre, precio, stock FROM productos WHERE id = %s AND activo = TRUE;', (id_producto,))
            prod = cursor.fetchone()

            if prod:
                nombre_prod = extraer_columna(prod, 'nombre', 1)
                precio_prod = float(extraer_columna(prod, 'precio', 2, 0.0))
                stock_prod = int(extraer_columna(prod, 'stock', 3, 0))

                if stock_prod <= 0:
                    omitidos_stock.append(f"{nombre_prod} (Agotado)")
                    continue

                prod_id_str = str(id_producto)
                cant_actual = carrito.get(prod_id_str, {}).get('cantidad', 0)
                nueva_cant = cant_actual + cant_solicitada

                if nueva_cant > stock_prod:
                    omitidos_stock.append(f"{nombre_prod} (Máx: {stock_prod})")
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

        total_unidades_carrito = sum(int(item.get('cantidad', 0)) for item in carrito.values())

        if agregados_count > 0:
            msg_ok = f'¡Se agregaron con éxito {agregados_count} producto(s) seleccionados al carrito!'
            flash(msg_ok, 'success')
        else:
            msg_ok = 'No se pudieron agregar los productos seleccionados por falta de stock disponible.'

        if es_peticion_json:
            status_resp = "success" if agregados_count > 0 else "error"
            code_resp = 200 if agregados_count > 0 else 400
            return jsonify({
                "status": status_resp,
                "mensaje": msg_ok,
                "afectados": agregados_count,
                "omitidos": omitidos_stock,
                "carrito_items": len(carrito),
                "carrito_unidades": total_unidades_carrito,
                "redirect_url": url_for('ver_carrito')
            }), code_resp

        return redirect(url_for('ver_carrito'))

    except Exception as e:
        msg_ex = f'Error al procesar la selección múltiple: {e}'
        if es_peticion_json:
            return jsonify({
                "status": "error",
                "mensaje": msg_ex,
                "afectados": 0
            }), 500
        flash(msg_ex, 'danger')
        return redirect(url_for('productos'))
    finally:
        conn.close()

# ==============================================================================
# MÓDULO 5: AUDITORÍA DEL SISTEMA (EXCLUSIVO PARA ADMINISTRADORES)
# ==============================================================================
@app.route('/auditoria')
@login_required
@roles_requeridos('admin')
def auditoria():
    conn = obtener_conexion()
    registros_auditoria = []
    tablas_disponibles = []

    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    per_page = 15
    offset = (page - 1) * per_page

    # Filtros por query params (soporta nombres completos y abreviados)
    tabla_filtro = (request.args.get('tabla_afectada') or request.args.get('tabla') or '').strip()
    operacion_filtro = (request.args.get('operacion') or '').strip().upper()
    usuario_filtro = (request.args.get('usuario') or '').strip()
    fecha_desde = (request.args.get('fecha_desde') or request.args.get('desde') or '').strip()
    fecha_hasta = (request.args.get('fecha_hasta') or request.args.get('hasta') or '').strip()

    total_items = 0
    total_pages = 1

    if conn:
        try:
            cursor = conn.cursor()

            # 1. Obtener listado dinámico de tablas registradas en auditoría para el selector
            cursor.execute('''
                SELECT DISTINCT tabla_afectada 
                FROM auditoria 
                WHERE tabla_afectada IS NOT NULL 
                ORDER BY tabla_afectada ASC;
            ''')
            filas_tablas = cursor.fetchall()
            tablas_disponibles = [
                str(extraer_columna(t, 'tabla_afectada', 0))
                for t in filas_tablas
                if extraer_columna(t, 'tabla_afectada', 0)
            ]

            # 2. Construcción segura y parametrizada de cláusulas WHERE
            where_clauses = ["1=1"]
            params = []

            if tabla_filtro:
                where_clauses.append("a.tabla_afectada = %s")
                params.append(tabla_filtro)

            if operacion_filtro in ('INSERT', 'UPDATE', 'SOFT_DELETE', 'DELETE'):
                where_clauses.append("UPPER(a.operacion) = %s")
                params.append(operacion_filtro)

            if usuario_filtro:
                where_clauses.append("COALESCE(a.usuario, '') ILIKE %s")
                params.append(f"%{usuario_filtro}%")

            if fecha_desde:
                where_clauses.append("DATE(a.fecha_hora) >= %s")
                params.append(fecha_desde)

            if fecha_hasta:
                where_clauses.append("DATE(a.fecha_hora) <= %s")
                params.append(fecha_hasta)

            where_sql = "WHERE " + " AND ".join(where_clauses)

            # 3. Conteo total de registros filtrados
            cursor.execute(f'''
                SELECT COUNT(*) AS total
                FROM auditoria a
                {where_sql};
            ''', tuple(params))
            row_count = cursor.fetchone()
            total_items = int(extraer_columna(row_count, 'total', 0, 0))
            total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

            # 4. Consulta paginada ordenada por fecha_hora DESC
            query_datos = f'''
                SELECT a.id_auditoria,
                       a.tabla_afectada,
                       a.operacion,
                       a.id_registro,
                       a.datos_previos,
                       a.datos_nuevos,
                       COALESCE(a.usuario, 'system') AS usuario,
                       a.fecha_hora
                FROM auditoria a
                {where_sql}
                ORDER BY a.fecha_hora DESC, a.id_auditoria DESC
                LIMIT %s OFFSET %s;
            '''
            params_datos = list(params) + [per_page, offset]
            cursor.execute(query_datos, tuple(params_datos))
            filas = cursor.fetchall()
            cursor.close()

            for fila in filas:
                fecha_raw = extraer_columna(fila, 'fecha_hora', 7)
                if hasattr(fecha_raw, 'strftime'):
                    fecha_fmt = fecha_raw.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    fecha_fmt = str(fecha_raw or '')

                registros_auditoria.append({
                    'id_auditoria': extraer_columna(fila, 'id_auditoria', 0),
                    'tabla_afectada': extraer_columna(fila, 'tabla_afectada', 1, 'N/A'),
                    'operacion': str(extraer_columna(fila, 'operacion', 2, '')).upper(),
                    'id_registro': extraer_columna(fila, 'id_registro', 3),
                    'datos_previos': extraer_columna(fila, 'datos_previos', 4),
                    'datos_nuevos': extraer_columna(fila, 'datos_nuevos', 5),
                    'usuario': extraer_columna(fila, 'usuario', 6, 'system'),
                    'fecha_hora': fecha_fmt
                })

        except Exception as e:
            flash(f"Error al consultar el historial de auditoría: {e}", "danger")
        finally:
            conn.close()
    else:
        flash("Error de conexión con la base de datos.", "danger")

    # Asegurar opciones base en el filtro de tablas aunque la tabla aún esté vacía
    tablas_base = ['usuarios', 'clientes', 'proveedores', 'productos', 'facturas', 'detalle_facturas']
    for tb in tablas_base:
        if tb not in tablas_disponibles:
            tablas_disponibles.append(tb)
    tablas_disponibles.sort()

    paginador = Paginacion(
        items=registros_auditoria,
        total_registros=total_items,
        pagina_actual=page,
        por_pagina=per_page
    )

    return render_template(
        'auditoria.html',
        registros=paginador.items,
        paginador=paginador,
        tablas_disponibles=tablas_disponibles,
        sistema=SISTEMA_INFO,
        page=paginador.pagina_actual,
        total_pages=paginador.total_paginas,
        total_items=paginador.total_registros,
        per_page=per_page,
        filtros={
            'tabla_afectada': tabla_filtro,
            'operacion': operacion_filtro,
            'usuario': usuario_filtro,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta
        }
    )


# 5.1 EXPORTACIÓN DE AUDITORÍA A CSV (SIN LIMIT NI OFFSET, CON BOM UTF-8)
@app.route('/auditoria/exportar')
@login_required
@roles_requeridos('admin')
def exportar_auditoria():
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión con la base de datos al exportar.", "danger")
        return redirect(url_for('auditoria'))

    # Captura de filtros (soporta tanto 'tabla'/'desde'/'hasta' como 'tabla_afectada'/'fecha_desde'/'fecha_hasta')
    tabla_filtro = (request.args.get('tabla_afectada') or request.args.get('tabla') or '').strip()
    operacion_filtro = (request.args.get('operacion') or '').strip().upper()
    usuario_filtro = (request.args.get('usuario') or '').strip()
    fecha_desde = (request.args.get('fecha_desde') or request.args.get('desde') or '').strip()
    fecha_hasta = (request.args.get('fecha_hasta') or request.args.get('hasta') or '').strip()

    try:
        cursor = conn.cursor()

        where_clauses = ["1=1"]
        params = []

        if tabla_filtro:
            where_clauses.append("a.tabla_afectada = %s")
            params.append(tabla_filtro)

        if operacion_filtro in ('INSERT', 'UPDATE', 'SOFT_DELETE', 'DELETE'):
            where_clauses.append("UPPER(a.operacion) = %s")
            params.append(operacion_filtro)

        if usuario_filtro:
            where_clauses.append("COALESCE(a.usuario, '') ILIKE %s")
            params.append(f"%{usuario_filtro}%")

        if fecha_desde:
            where_clauses.append("DATE(a.fecha_hora) >= %s")
            params.append(fecha_desde)

        if fecha_hasta:
            where_clauses.append("DATE(a.fecha_hora) <= %s")
            params.append(fecha_hasta)

        where_sql = "WHERE " + " AND ".join(where_clauses)

        query_exportar = f'''
            SELECT a.id_auditoria,
                   a.fecha_hora,
                   COALESCE(a.usuario, 'system') AS usuario,
                   a.tabla_afectada,
                   a.operacion,
                   a.id_registro,
                   a.datos_previos,
                   a.datos_nuevos
            FROM auditoria a
            {where_sql}
            ORDER BY a.fecha_hora DESC, a.id_auditoria DESC;
        '''
        cursor.execute(query_exportar, tuple(params))
        filas = cursor.fetchall()
        cursor.close()

        # Generación en memoria del archivo CSV con BOM UTF-8 + instrucción nativa sep=; para Microsoft Excel
        output = io.StringIO()
        output.write('\ufeffsep=;\n')
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        # Cabeceras oficiales del reporte
        writer.writerow([
            'ID',
            'Fecha y Hora',
            'Usuario',
            'Tabla Afectada',
            'Operación',
            'ID Registro',
            'Datos Previos',
            'Datos Nuevos'
        ])

        for fila in filas:
            id_aud = extraer_columna(fila, 'id_auditoria', 0, '')
            fecha_raw = extraer_columna(fila, 'fecha_hora', 1)
            if hasattr(fecha_raw, 'strftime'):
                fecha_str = fecha_raw.strftime('%Y-%m-%d %H:%M:%S')
            else:
                fecha_str = str(fecha_raw or '')

            usuario_str = extraer_columna(fila, 'usuario', 2, 'system')
            tabla_str = extraer_columna(fila, 'tabla_afectada', 3, '')
            operacion_str = str(extraer_columna(fila, 'operacion', 4, '')).upper()
            id_reg = extraer_columna(fila, 'id_registro', 5, '')
            prev_raw = extraer_columna(fila, 'datos_previos', 6)
            nuev_raw = extraer_columna(fila, 'datos_nuevos', 7)

            prev_json = json.dumps(prev_raw, ensure_ascii=False) if prev_raw is not None else ''
            nuev_json = json.dumps(nuev_raw, ensure_ascii=False) if nuev_raw is not None else ''

            writer.writerow([
                id_aud,
                fecha_str,
                usuario_str,
                tabla_str,
                operacion_str,
                id_reg,
                prev_json,
                nuev_json
            ])

        csv_contenido = output.getvalue()
        output.close()

        nombre_archivo = f"auditoria_techmanager_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            csv_contenido,
            mimetype='text/csv; charset=utf-8',
            headers={
                "Content-Disposition": f"attachment; filename={nombre_archivo}"
            }
        )

    except Exception as e:
        flash(f"Error al exportar la bitácora de auditoría: {e}", "danger")
        return redirect(url_for('auditoria'))
    finally:
        conn.close()


# ==============================================================================
# MÓDULO 6: PERFIL DE USUARIO Y SEGURIDAD DE CUENTA
# ==============================================================================

def asegurar_columnas_perfil_usuarios(conn):
    """
    Garantiza que la tabla 'usuarios' en PostgreSQL cuente con las columnas
    nombre, telefono, cedula y direccion antes de consultar o actualizar el perfil.
    """
    try:
        cur = conn.cursor()
        cur.execute("""
            ALTER TABLE usuarios
                ADD COLUMN IF NOT EXISTS nombre VARCHAR(150) NULL,
                ADD COLUMN IF NOT EXISTS telefono VARCHAR(20) NULL,
                ADD COLUMN IF NOT EXISTS cedula VARCHAR(13) NULL,
                ADD COLUMN IF NOT EXISTS direccion TEXT NULL;
        """)
        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()


# 1. VISUALIZACIÓN DE PERFIL
@app.route('/perfil')
@login_required
def perfil():
    conn = obtener_conexion()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for('inicio'))

    asegurar_columnas_perfil_usuarios(conn)

    datos_perfil = {
        'id': current_user.id,
        'usuario': current_user.usuario,
        'nombre': getattr(current_user, 'nombre', '') or current_user.usuario,
        'email': getattr(current_user, 'email', '') or '',
        'telefono': '',
        'cedula': '',
        'direccion': '',
        'rol': getattr(current_user, 'rol', 'usuario'),
        'activo': True,
        'fecha_registro': None
    }

    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*,
                   c.nombre AS cliente_nombre,
                   c.telefono AS cliente_telefono,
                   c.ruc AS cliente_ruc
            FROM usuarios u
            LEFT JOIN clientes c ON c.usuario_id = u.id
            WHERE u.id = %s
            LIMIT 1;
        ''', (int(current_user.id),))
        fila = cursor.fetchone()
        cursor.close()

        if fila:
            if isinstance(fila, dict):
                nombre_val = fila.get('nombre') or fila.get('cliente_nombre') or fila.get('usuario')
                telefono_val = fila.get('telefono') or fila.get('cliente_telefono') or ''
                cedula_val = fila.get('cedula') or fila.get('cliente_ruc') or ''
                direccion_val = fila.get('direccion') or ''
                fecha_raw = fila.get('fecha_registro') or fila.get('created_at')
                if hasattr(fecha_raw, 'strftime'):
                    fecha_fmt = fecha_raw.strftime('%d/%m/%Y %H:%M')
                else:
                    fecha_fmt = str(fecha_raw) if fecha_raw else None

                datos_perfil.update({
                    'id': fila.get('id', current_user.id),
                    'usuario': fila.get('usuario', current_user.usuario),
                    'nombre': nombre_val,
                    'email': fila.get('email', ''),
                    'telefono': telefono_val,
                    'cedula': cedula_val,
                    'direccion': direccion_val,
                    'rol': (fila.get('rol') or 'usuario').lower(),
                    'activo': bool(fila.get('activo', True)),
                    'fecha_registro': fecha_fmt
                })
            else:
                datos_perfil['usuario'] = extraer_columna(fila, 'usuario', 1, current_user.usuario)
                datos_perfil['email'] = extraer_columna(fila, 'email', 2, '')

    except Exception as e:
        flash(f"Error al cargar la información del perfil: {e}", "danger")
    finally:
        conn.close()

    return render_template('perfil.html', perfil=datos_perfil, sistema=SISTEMA_INFO)


# 2. ACTUALIZACIÓN DE DATOS DEL PERFIL (DISPARA TRIGGER DE AUDITORÍA EN 'usuarios')
@app.route('/perfil/actualizar', methods=['POST'])
@login_required
def actualizar_perfil():
    nombre = request.form.get('nombre', '').strip()
    email = request.form.get('email', '').strip().lower()
    telefono = request.form.get('telefono', '').strip()
    cedula = request.form.get('cedula', '').strip()
    direccion = request.form.get('direccion', '').strip()

    if not nombre or len(nombre) < 3:
        flash('El nombre completo es obligatorio y debe contener al menos 3 caracteres.', 'warning')
        return redirect(url_for('perfil'))

    if not email or '@' not in email:
        flash('Debe ingresar una dirección de correo electrónico válida.', 'warning')
        return redirect(url_for('perfil'))

    if cedula and (not cedula.isdigit() or len(cedula) not in (10, 13)):
        flash('La Cédula o RUC debe contener únicamente números (10 o 13 dígitos).', 'warning')
        return redirect(url_for('perfil'))

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('perfil'))

    asegurar_columnas_perfil_usuarios(conn)

    try:
        cursor = conn.cursor()
        user_id = int(current_user.id)

        # 1. Validar que el email no esté en uso por otro ID de usuario diferente
        cursor.execute(
            'SELECT id FROM usuarios WHERE LOWER(email) = LOWER(%s) AND id != %s LIMIT 1;',
            (email, user_id)
        )
        if cursor.fetchone():
            cursor.close()
            flash('El correo electrónico ingresado ya está registrado por otro usuario.', 'warning')
            return redirect(url_for('perfil'))

        # 2. Validar que la cédula/RUC no esté repetida en otro registro de 'usuarios' ni 'clientes'
        if cedula:
            cursor.execute(
                'SELECT id FROM usuarios WHERE cedula = %s AND id != %s LIMIT 1;',
                (cedula, user_id)
            )
            if cursor.fetchone():
                cursor.close()
                flash('El número de Cédula / RUC ingresado ya se encuentra asociado a otro usuario.', 'warning')
                return redirect(url_for('perfil'))

            cursor.execute(
                'SELECT id FROM clientes WHERE ruc = %s AND (usuario_id IS NULL OR usuario_id != %s) LIMIT 1;',
                (cedula, user_id)
            )
            if cursor.fetchone():
                cursor.close()
                flash('El número de Cédula / RUC ya pertenece a otro cliente registrado en el directorio.', 'warning')
                return redirect(url_for('perfil'))

        # 3. Ejecutar UPDATE parametrizado sobre 'usuarios' (dispara el trigger de auditoría)
        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'usuarios';
        ''')
        cols_usuarios = {extraer_columna(c, 'column_name', 0) for c in cursor.fetchall()}

        set_clauses = [
            "nombre = %s",
            "email = %s",
            "telefono = %s",
            "cedula = %s",
            "direccion = %s"
        ]
        params_update = [
            nombre,
            email,
            telefono or None,
            cedula or None,
            direccion or None
        ]

        if 'modified_by' in cols_usuarios:
            set_clauses.append("modified_by = %s")
            params_update.append(current_user.usuario)

        params_update.append(user_id)
        cursor.execute(
            f"UPDATE usuarios SET {', '.join(set_clauses)} WHERE id = %s;",
            tuple(params_update)
        )

        # 4. Sincronizar también con la ficha en 'clientes' si el usuario tiene perfil comercial asociado
        cursor.execute('SELECT id FROM clientes WHERE usuario_id = %s LIMIT 1;', (user_id,))
        cli_row = cursor.fetchone()
        if cli_row:
            cli_id = extraer_columna(cli_row, 'id', 0)
            cursor.execute('''
                UPDATE clientes
                SET nombre = %s,
                    email = %s,
                    telefono = CASE WHEN %s != '' THEN %s ELSE telefono END,
                    ruc = CASE WHEN %s != '' THEN %s ELSE ruc END,
                    modified_by = %s
                WHERE id = %s;
            ''', (nombre, email, telefono, telefono, cedula, cedula, current_user.usuario, cli_id))

        conn.commit()
        cursor.close()
        flash('Los datos de su perfil, identificación y domicilio han sido actualizados exitosamente.', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Error al actualizar el perfil: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('perfil'))


# 3. CAMBIO DE CONTRASEÑA DESDE EL PERFIL
@app.route('/perfil/cambiar-password', methods=['POST'])
@login_required
def cambiar_password_perfil():
    password_actual = request.form.get('password_actual', '')
    nueva_password = request.form.get('nueva_password', '')
    confirmar_password = request.form.get('confirmar_password', '')

    if not password_actual or not nueva_password or not confirmar_password:
        flash('Debe completar todos los campos de contraseña.', 'warning')
        return redirect(url_for('perfil'))

    if len(nueva_password) < 6:
        flash('La nueva contraseña debe tener al menos 6 caracteres.', 'warning')
        return redirect(url_for('perfil'))

    if nueva_password != confirmar_password:
        flash('La nueva contraseña y su confirmación no coinciden.', 'danger')
        return redirect(url_for('perfil'))

    conn = obtener_conexion()
    if not conn:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('perfil'))

    try:
        cursor = conn.cursor()
        user_id = int(current_user.id)

        cursor.execute('SELECT password FROM usuarios WHERE id = %s LIMIT 1;', (user_id,))
        fila = cursor.fetchone()

        if not fila:
            cursor.close()
            flash('No se encontró el registro de usuario.', 'danger')
            return redirect(url_for('perfil'))

        hash_actual = extraer_columna(fila, 'password', 0, '')

        if not check_password_hash(hash_actual, password_actual):
            cursor.close()
            flash('La contraseña actual ingresada es incorrecta.', 'danger')
            return redirect(url_for('perfil'))

        nuevo_hash = generate_password_hash(nueva_password)

        cursor.execute('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'usuarios' AND column_name = 'modified_by';
        ''')
        tiene_modified_by = cursor.fetchone() is not None

        if tiene_modified_by:
            cursor.execute(
                'UPDATE usuarios SET password = %s, modified_by = %s WHERE id = %s;',
                (nuevo_hash, current_user.usuario, user_id)
            )
        else:
            cursor.execute(
                'UPDATE usuarios SET password = %s WHERE id = %s;',
                (nuevo_hash, user_id)
            )

        conn.commit()
        cursor.close()
        flash('Su contraseña ha sido actualizada correctamente.', 'success')

    except Exception as e:
        conn.rollback()
        flash(f'Error al cambiar la contraseña: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('perfil'))


# INICIO DE LA APLICACIÓN
if __name__ == '__main__':
    app.run(debug=True)
