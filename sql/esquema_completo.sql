-- ==============================================================================
-- PROYECTO INTEGRADOR: TECHMANAGER SYSTEM (v2.0.0)
-- SCRIPT UNIFICADO DE BASE DE DATOS PARA PRODUCCIÓN (PostgreSQL 16+ / Supabase / Render)
-- Archivo único: sql/esquema_completo.sql
-- ==============================================================================

-- ==============================================================================
-- PASO 1: TRANSACCIÓN Y LIMPIEZA INICIAL SEGURA (FUNCIONES, TRIGGERS Y TABLAS)
-- ==============================================================================

BEGIN;

SET search_path TO public;

-- Al usar DROP FUNCTION ... CASCADE y DROP TABLE ... CASCADE, PostgreSQL elimina
-- automáticamente todos los triggers asociados sin fallar con ERROR 42P01 cuando
-- las tablas aún no existen en un despliegue limpio (ej. Supabase / Render).
DROP FUNCTION IF EXISTS public.fn_auditoria_general() CASCADE;
DROP FUNCTION IF EXISTS public.fn_registrar_auditoria() CASCADE;
DROP FUNCTION IF EXISTS public.fn_descontar_stock_detalle() CASCADE;
DROP FUNCTION IF EXISTS public.fn_reintegrar_stock_nc() CASCADE;
DROP FUNCTION IF EXISTS public.obtener_siguiente_secuencial_nc() CASCADE;
DROP FUNCTION IF EXISTS public.fn_sync_clientes() CASCADE;
DROP FUNCTION IF EXISTS public.fn_sync_proveedores() CASCADE;
DROP FUNCTION IF EXISTS public.fn_sync_facturas() CASCADE;

DROP TABLE IF EXISTS public.auditoria CASCADE;
DROP TABLE IF EXISTS public.detalle_notas_credito CASCADE;
DROP TABLE IF EXISTS public.notas_credito CASCADE;
DROP TABLE IF EXISTS public.detalle_facturas CASCADE;
DROP TABLE IF EXISTS public.facturas CASCADE;
DROP TABLE IF EXISTS public.productos CASCADE;
DROP TABLE IF EXISTS public.proveedores CASCADE;
DROP TABLE IF EXISTS public.clientes CASCADE;
DROP TABLE IF EXISTS public.usuarios CASCADE;
DROP TABLE IF EXISTS public.metodos_pago CASCADE;
DROP TABLE IF EXISTS public.ciudades CASCADE;
DROP TABLE IF EXISTS public.estados_factura CASCADE;
DROP TABLE IF EXISTS public.marcas CASCADE;
DROP TABLE IF EXISTS public.categorias CASCADE;
DROP TABLE IF EXISTS public.roles CASCADE;

-- ==============================================================================
-- PASO 2: CREACIÓN DE TABLAS MAESTRAS INDEPENDIENTES
-- (roles, categorias, marcas, estados_factura, ciudades, metodos_pago)
-- ==============================================================================

-- 2.1 Tabla de Roles del Sistema
CREATE TABLE public.roles (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT NULL
);

-- 2.2 Catálogo de Categorías
CREATE TABLE public.categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2.3 Catálogo de Marcas
CREATE TABLE public.marcas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2.4 Estados de Factura SRI (1: PENDIENTE, 2: PAGADA, 3: ANULADA)
CREATE TABLE public.estados_factura (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    codigo VARCHAR(20) NOT NULL UNIQUE
);

-- 2.5 Catálogo de Ciudades
CREATE TABLE public.ciudades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_ciudad_provincia UNIQUE (nombre, provincia)
);

-- 2.6 Métodos de Pago SRI
CREATE TABLE public.metodos_pago (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    codigo_sri VARCHAR(5) DEFAULT '01'
);

-- ==============================================================================
-- PASO 3: CREACIÓN DE TABLAS PRINCIPALES
-- (usuarios, clientes, proveedores, productos)
-- ==============================================================================

-- 3.1 Tabla de Usuarios (Autenticación, Roles y Control de Acceso)
CREATE TABLE public.usuarios (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    cedula VARCHAR(13) UNIQUE NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'cliente',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Columnas extendidas de perfil y seguridad operativa
    nombre VARCHAR(150) NULL,
    telefono VARCHAR(20) NULL,
    direccion TEXT NULL,
    id_rol INT NULL,
    intentos_fallidos INT NOT NULL DEFAULT 0,
    bloqueado_hasta TIMESTAMP NULL,
    created_by VARCHAR(50) DEFAULT 'sistema',
    modified_by VARCHAR(50) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usuario_rol FOREIGN KEY (id_rol)
        REFERENCES public.roles(id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- 3.2 Directorio de Clientes
CREATE TABLE public.clientes (
    id SERIAL PRIMARY KEY,
    nombres VARCHAR(100) NOT NULL DEFAULT '',
    apellidos VARCHAR(100) NOT NULL DEFAULT '',
    cedula_ruc VARCHAR(13) UNIQUE NULL,
    direccion TEXT NULL DEFAULT 'Machala - Ecuador',
    telefono VARCHAR(20) NOT NULL,
    email VARCHAR(120) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Columnas de compatibilidad con consultas del ERP (app.py)
    nombre VARCHAR(150) NOT NULL DEFAULT '',
    ruc VARCHAR(13) UNIQUE NULL,
    id_ciudad INT DEFAULT 1,
    usuario_id INT NULL,
    created_by VARCHAR(50) DEFAULT 'sistema',
    modified_by VARCHAR(50) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cliente_ciudad FOREIGN KEY (id_ciudad)
        REFERENCES public.ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cliente_usuario FOREIGN KEY (usuario_id)
        REFERENCES public.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- 3.3 Directorio de Proveedores
CREATE TABLE public.proveedores (
    id SERIAL PRIMARY KEY,
    razon_social VARCHAR(150) NOT NULL DEFAULT '',
    ruc VARCHAR(13) UNIQUE NULL,
    direccion TEXT NULL DEFAULT 'Ecuador',
    telefono VARCHAR(20) NOT NULL,
    email VARCHAR(120) NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Columnas de compatibilidad con consultas del ERP (app.py)
    nombre VARCHAR(150) NOT NULL DEFAULT '',
    contacto VARCHAR(150) NULL,
    id_categoria INT NOT NULL DEFAULT 1,
    id_ciudad INT DEFAULT 1,
    created_by VARCHAR(50) DEFAULT 'sistema',
    modified_by VARCHAR(50) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_proveedor_categoria FOREIGN KEY (id_categoria)
        REFERENCES public.categorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_proveedor_ciudad FOREIGN KEY (id_ciudad)
        REFERENCES public.ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 3.4 Catálogo de Productos (Inventario)
CREATE TABLE public.productos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    precio NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    imagen VARCHAR(255) NOT NULL DEFAULT 'default_producto.png',
    id_categoria INT NOT NULL,
    id_marca INT NOT NULL DEFAULT 1,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'sistema',
    modified_by VARCHAR(50) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_producto_categoria FOREIGN KEY (id_categoria)
        REFERENCES public.categorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_producto_marca FOREIGN KEY (id_marca)
        REFERENCES public.marcas(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- ==============================================================================
-- PASO 4: CREACIÓN DE TABLAS TRANSACCIONALES
-- (facturas, detalle_facturas, auditoria)
-- ==============================================================================

-- 4.1 Cabecera de Facturas Electrónicas (RIDE / SRI)
CREATE TABLE public.facturas (
    id SERIAL PRIMARY KEY,
    numero VARCHAR(30) NOT NULL UNIQUE,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    id_cliente INT NOT NULL,
    id_usuario INT NULL,
    subtotal_15 NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal_15 >= 0),
    subtotal_0 NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal_0 >= 0),
    iva NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (iva >= 0),
    total NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (total >= 0),
    id_estado INT NOT NULL DEFAULT 2,
    forma_pago VARCHAR(50) NOT NULL DEFAULT 'EFECTIVO',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observacion_anulacion TEXT NULL,
    -- Columnas de compatibilidad operativa con app.py
    monto NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (monto >= 0),
    id_metodo_pago INT DEFAULT 1,
    created_by VARCHAR(50) DEFAULT 'sistema',
    modified_by VARCHAR(50) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_factura_cliente FOREIGN KEY (id_cliente)
        REFERENCES public.clientes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_factura_usuario FOREIGN KEY (id_usuario)
        REFERENCES public.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_factura_estado FOREIGN KEY (id_estado)
        REFERENCES public.estados_factura(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_factura_metodo FOREIGN KEY (id_metodo_pago)
        REFERENCES public.metodos_pago(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 4.2 Detalle de Facturas
CREATE TABLE public.detalle_facturas (
    id SERIAL PRIMARY KEY,
    id_factura INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal >= 0),
    iva NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (iva >= 0),
    total NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (total >= 0),
    CONSTRAINT uq_detalle_factura_producto UNIQUE (id_factura, id_producto),
    CONSTRAINT fk_detalle_factura FOREIGN KEY (id_factura)
        REFERENCES public.facturas(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto)
        REFERENCES public.productos(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 4.3 Cabecera de Notas de Crédito Electrónicas (RIDE / SRI Código 04)
CREATE TABLE public.notas_credito (
    id SERIAL PRIMARY KEY,
    id_factura INT NOT NULL,
    establecimiento VARCHAR(3) NOT NULL DEFAULT '001',
    punto_emision VARCHAR(3) NOT NULL DEFAULT '001',
    secuencial VARCHAR(9) NOT NULL,
    numero_comprobante VARCHAR(30) GENERATED ALWAYS AS (establecimiento || '-' || punto_emision || '-' || secuencial) STORED UNIQUE,
    fecha_emision DATE NOT NULL DEFAULT CURRENT_DATE,
    numero_factura_modificada VARCHAR(30) NOT NULL,
    fecha_emision_factura_modificada DATE NOT NULL DEFAULT CURRENT_DATE,
    motivo_modificacion TEXT NOT NULL,
    subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal >= 0),
    iva NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (iva >= 0),
    total NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (total >= 0),
    estado VARCHAR(20) NOT NULL DEFAULT 'EMITIDA',
    usuario_creacion VARCHAR(50) DEFAULT 'sistema',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_nc_factura FOREIGN KEY (id_factura)
        REFERENCES public.facturas(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 4.4 Detalle de Notas de Crédito
CREATE TABLE public.detalle_notas_credito (
    id SERIAL PRIMARY KEY,
    id_nota_credito INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal >= 0),
    iva NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (iva >= 0),
    total NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (total >= 0),
    CONSTRAINT fk_detalle_nc FOREIGN KEY (id_nota_credito)
        REFERENCES public.notas_credito(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_detalle_nc_producto FOREIGN KEY (id_producto)
        REFERENCES public.productos(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 4.5 Tabla Centralizada de Auditoría (Trazabilidad JSONB)
CREATE TABLE public.auditoria (
    id SERIAL PRIMARY KEY,
    id_auditoria INT GENERATED ALWAYS AS (id) STORED,
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario VARCHAR(50) NOT NULL DEFAULT 'sistema',
    tabla_afectada VARCHAR(50) NOT NULL,
    operacion VARCHAR(20) NOT NULL,
    id_registro INT NOT NULL,
    datos_previos JSONB NULL,
    datos_nuevos JSONB NULL
);

-- ==============================================================================
-- PASO 5: CREACIÓN DE FUNCIONES PL/pgSQL Y TRIGGERS
-- (Se crean estrictamente después de existir todas las tablas del esquema)
-- ==============================================================================

-- 5.1 Función y Trigger de sincronización en clientes
CREATE OR REPLACE FUNCTION public.fn_sync_clientes()
RETURNS TRIGGER AS $$
BEGIN
    IF (NEW.nombre IS NULL OR btrim(NEW.nombre) = '') THEN
        NEW.nombre := btrim(COALESCE(NEW.nombres, '') || ' ' || COALESCE(NEW.apellidos, ''));
    END IF;

    IF (NEW.nombres IS NULL OR btrim(NEW.nombres) = '') AND (NEW.nombre IS NOT NULL AND btrim(NEW.nombre) <> '') THEN
        NEW.nombres := split_part(btrim(NEW.nombre), ' ', 1);
        NEW.apellidos := COALESCE(NULLIF(btrim(substring(btrim(NEW.nombre) FROM length(split_part(btrim(NEW.nombre), ' ', 1)) + 1)), ''), 'S/A');
    END IF;

    IF NEW.cedula_ruc IS NULL AND NEW.ruc IS NOT NULL THEN
        NEW.cedula_ruc := NEW.ruc;
    ELSIF NEW.ruc IS NULL AND NEW.cedula_ruc IS NOT NULL THEN
        NEW.ruc := NEW.cedula_ruc;
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.ruc IS DISTINCT FROM OLD.ruc THEN
            NEW.cedula_ruc := NEW.ruc;
        ELSIF NEW.cedula_ruc IS DISTINCT FROM OLD.cedula_ruc THEN
            NEW.ruc := NEW.cedula_ruc;
        END IF;
    END IF;

    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_clientes
BEFORE INSERT OR UPDATE ON public.clientes
FOR EACH ROW EXECUTE FUNCTION public.fn_sync_clientes();

-- 5.2 Función y Trigger de sincronización en proveedores
CREATE OR REPLACE FUNCTION public.fn_sync_proveedores()
RETURNS TRIGGER AS $$
BEGIN
    IF (NEW.nombre IS NULL OR btrim(NEW.nombre) = '') AND (NEW.razon_social IS NOT NULL AND btrim(NEW.razon_social) <> '') THEN
        NEW.nombre := btrim(NEW.razon_social);
    ELSIF (NEW.razon_social IS NULL OR btrim(NEW.razon_social) = '') AND (NEW.nombre IS NOT NULL AND btrim(NEW.nombre) <> '') THEN
        NEW.razon_social := btrim(NEW.nombre);
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.nombre IS DISTINCT FROM OLD.nombre THEN
            NEW.razon_social := NEW.nombre;
        ELSIF NEW.razon_social IS DISTINCT FROM OLD.razon_social THEN
            NEW.nombre := NEW.razon_social;
        END IF;
    END IF;

    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_proveedores
BEFORE INSERT OR UPDATE ON public.proveedores
FOR EACH ROW EXECUTE FUNCTION public.fn_sync_proveedores();

-- 5.3 Función y Trigger de sincronización fiscal en facturas
CREATE OR REPLACE FUNCTION public.fn_sync_facturas()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total IS NULL OR NEW.total = 0 THEN
        NEW.total := COALESCE(NEW.monto, 0.00);
    END IF;

    IF NEW.monto IS NULL OR NEW.monto = 0 THEN
        NEW.monto := COALESCE(NEW.total, 0.00);
    ELSIF TG_OP = 'UPDATE' AND NEW.monto IS DISTINCT FROM OLD.monto THEN
        NEW.total := NEW.monto;
    ELSIF TG_OP = 'UPDATE' AND NEW.total IS DISTINCT FROM OLD.total THEN
        NEW.monto := NEW.total;
    END IF;

    IF (NEW.subtotal_15 IS NULL OR NEW.subtotal_15 = 0) AND NEW.total > 0 THEN
        NEW.subtotal_15 := ROUND(NEW.total / 1.15, 2);
        NEW.iva := ROUND(NEW.total - NEW.subtotal_15, 2);
    END IF;

    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_facturas
BEFORE INSERT OR UPDATE ON public.facturas
FOR EACH ROW EXECUTE FUNCTION public.fn_sync_facturas();

-- 5.4 Función y Trigger de control de stock en detalle_facturas
CREATE OR REPLACE FUNCTION public.fn_descontar_stock_detalle()
RETURNS TRIGGER AS $$
DECLARE
    v_estado INT;
    v_es_nueva BOOLEAN;
BEGIN
    IF NEW.subtotal IS NULL OR NEW.subtotal = 0 THEN
        NEW.subtotal := ROUND(NEW.cantidad * NEW.precio_unitario, 2);
    END IF;

    IF NEW.iva IS NULL OR NEW.iva = 0 THEN
        NEW.iva := ROUND(NEW.subtotal * 0.15, 2);
    END IF;

    IF NEW.total IS NULL OR NEW.total = 0 THEN
        NEW.total := ROUND(NEW.subtotal + NEW.iva, 2);
    END IF;

    -- Si se están cargando semillas iniciales (seed_mode = 'on'), conservar el stock inicial
    IF COALESCE(current_setting('app.seed_mode', true), 'off') = 'on' THEN
        RETURN NEW;
    END IF;

    SELECT id_estado, (xmin::text = (txid_current() % (2^32)::bigint)::text)
    INTO v_estado, v_es_nueva
    FROM public.facturas
    WHERE id = NEW.id_factura;

    IF COALESCE(v_es_nueva, TRUE) AND COALESCE(v_estado, 2) != 3 THEN
        UPDATE public.productos
        SET stock = stock - NEW.cantidad,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id_producto;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_descontar_stock_detalle
BEFORE INSERT ON public.detalle_facturas
FOR EACH ROW EXECUTE FUNCTION public.fn_descontar_stock_detalle();

-- 5.5 Función genérica de Auditoría General y Triggers AFTER INSERT OR UPDATE OR DELETE
CREATE OR REPLACE FUNCTION public.fn_auditoria_general()
RETURNS TRIGGER AS $$
DECLARE
    v_operacion VARCHAR(20);
    v_usuario VARCHAR(50);
    v_id_registro INT;
    v_old_json JSONB;
    v_new_json JSONB;
BEGIN
    v_usuario := NULLIF(btrim(COALESCE(current_setting('app.current_user', true), '')), '');

    IF TG_OP = 'INSERT' THEN
        v_new_json := to_jsonb(NEW);
        v_id_registro := COALESCE((v_new_json->>'id')::INT, 0);
        v_usuario := COALESCE(
            v_usuario,
            NULLIF(v_new_json->>'modified_by', ''),
            NULLIF(v_new_json->>'created_by', ''),
            SESSION_USER,
            'sistema'
        );
        v_operacion := 'INSERT';

        INSERT INTO public.auditoria (fecha_hora, usuario, tabla_afectada, operacion, id_registro, datos_previos, datos_nuevos)
        VALUES (CURRENT_TIMESTAMP, v_usuario, TG_TABLE_NAME, v_operacion, v_id_registro, NULL, v_new_json);

        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        v_old_json := to_jsonb(OLD);
        v_new_json := to_jsonb(NEW);
        v_id_registro := COALESCE((v_new_json->>'id')::INT, (v_old_json->>'id')::INT, 0);
        v_usuario := COALESCE(
            v_usuario,
            NULLIF(v_new_json->>'modified_by', ''),
            NULLIF(v_new_json->>'created_by', ''),
            SESSION_USER,
            'sistema'
        );

        IF COALESCE((v_old_json->>'activo')::BOOLEAN, TRUE) IS TRUE
           AND COALESCE((v_new_json->>'activo')::BOOLEAN, TRUE) IS FALSE THEN
            v_operacion := 'SOFT_DELETE';
        ELSE
            v_operacion := 'UPDATE';
        END IF;

        INSERT INTO public.auditoria (fecha_hora, usuario, tabla_afectada, operacion, id_registro, datos_previos, datos_nuevos)
        VALUES (CURRENT_TIMESTAMP, v_usuario, TG_TABLE_NAME, v_operacion, v_id_registro, v_old_json, v_new_json);

        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        v_old_json := to_jsonb(OLD);
        v_id_registro := COALESCE((v_old_json->>'id')::INT, 0);
        v_usuario := COALESCE(
            v_usuario,
            NULLIF(v_old_json->>'modified_by', ''),
            NULLIF(v_old_json->>'created_by', ''),
            SESSION_USER,
            'sistema'
        );
        v_operacion := 'DELETE';

        INSERT INTO public.auditoria (fecha_hora, usuario, tabla_afectada, operacion, id_registro, datos_previos, datos_nuevos)
        VALUES (CURRENT_TIMESTAMP, v_usuario, TG_TABLE_NAME, v_operacion, v_id_registro, v_old_json, NULL);

        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Alias de compatibilidad
CREATE OR REPLACE FUNCTION public.fn_registrar_auditoria()
RETURNS TRIGGER AS $$
BEGIN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditoria_productos
AFTER INSERT OR UPDATE OR DELETE ON public.productos
FOR EACH ROW EXECUTE FUNCTION public.fn_auditoria_general();

CREATE TRIGGER trg_auditoria_clientes
AFTER INSERT OR UPDATE OR DELETE ON public.clientes
FOR EACH ROW EXECUTE FUNCTION public.fn_auditoria_general();

CREATE TRIGGER trg_auditoria_proveedores
AFTER INSERT OR UPDATE OR DELETE ON public.proveedores
FOR EACH ROW EXECUTE FUNCTION public.fn_auditoria_general();

CREATE TRIGGER trg_auditoria_facturas
AFTER INSERT OR UPDATE OR DELETE ON public.facturas
FOR EACH ROW EXECUTE FUNCTION public.fn_auditoria_general();

CREATE TRIGGER trg_auditoria_usuarios
AFTER INSERT OR UPDATE OR DELETE ON public.usuarios
FOR EACH ROW EXECUTE FUNCTION public.fn_auditoria_general();

CREATE TRIGGER trg_auditoria_notas_credito
AFTER INSERT OR UPDATE OR DELETE ON public.notas_credito
FOR EACH ROW EXECUTE FUNCTION public.fn_auditoria_general();

-- 5.6 Función para obtener el siguiente secuencial SRI de Nota de Crédito (001-001-XXXXXXXXX)
CREATE OR REPLACE FUNCTION public.obtener_siguiente_secuencial_nc()
RETURNS VARCHAR AS $$
DECLARE
    v_siguiente INT;
BEGIN
    SELECT COALESCE(MAX(id), 0) + 1
    INTO v_siguiente
    FROM public.notas_credito;

    RETURN '001-001-' || LPAD(v_siguiente::TEXT, 9, '0');
END;
$$ LANGUAGE plpgsql;

-- 5.7 Función y Trigger para reintegrar automáticamente el stock al emitir detalle de Nota de Crédito
CREATE OR REPLACE FUNCTION public.fn_reintegrar_stock_nc()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.subtotal IS NULL OR NEW.subtotal = 0 THEN
        NEW.subtotal := ROUND(NEW.cantidad * NEW.precio_unitario, 2);
    END IF;

    IF NEW.iva IS NULL OR NEW.iva = 0 THEN
        NEW.iva := ROUND(NEW.subtotal * 0.15, 2);
    END IF;

    IF NEW.total IS NULL OR NEW.total = 0 THEN
        NEW.total := ROUND(NEW.subtotal + NEW.iva, 2);
    END IF;

    UPDATE public.productos
    SET stock = stock + NEW.cantidad,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id_producto;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reintegrar_stock_nc
BEFORE INSERT ON public.detalle_notas_credito
FOR EACH ROW EXECUTE FUNCTION public.fn_reintegrar_stock_nc();

-- ==============================================================================
-- PASO 6: CREACIÓN DE ÍNDICES DE OPTIMIZACIÓN
-- ==============================================================================

CREATE INDEX idx_productos_activo ON public.productos(activo);
CREATE INDEX idx_clientes_cedula_ruc ON public.clientes(cedula_ruc);
CREATE INDEX idx_clientes_ruc ON public.clientes(ruc);
CREATE INDEX idx_facturas_numero_estado ON public.facturas(numero, id_estado);
CREATE INDEX idx_notas_credito_factura ON public.notas_credito(id_factura);
CREATE INDEX idx_auditoria_tabla_fecha ON public.auditoria(tabla_afectada, fecha_hora DESC);

-- ==============================================================================
-- PASO 7: INSERCIÓN DE DATOS INICIALES (SEEDS) EN ORDEN DE DEPENDENCIAS FORÁNEAS
-- ==============================================================================

SET LOCAL app.seed_mode = 'on';

-- 7.1 Roles base
INSERT INTO public.roles (id, nombre, descripcion) VALUES
(1, 'admin', 'Administrador general con control total de inventario, facturación SRI y auditoría'),
(2, 'cliente', 'Cliente externo con acceso al catálogo, carrito de compras y descarga de RIDE'),
(3, 'operador', 'Operador comercial de facturación, inventario y atención al cliente');
SELECT setval(pg_get_serial_sequence('public.roles', 'id'), (SELECT MAX(id) FROM public.roles));

-- 7.2 Categorías base
INSERT INTO public.categorias (id, nombre, descripcion, activo) VALUES
(1, 'Hardware', 'Servidores, estaciones de trabajo, periféricos y equipamiento físico empresarial', TRUE),
(2, 'Software', 'Sistemas operativos corporativos, suites de gestión y aplicativos', TRUE),
(3, 'Redes', 'Switches administrables, routers de borde, cableado estructurado y access points', TRUE),
(4, 'Licencias', 'Suscripciones de seguridad perimetral, bases de datos y software empresarial', TRUE);
SELECT setval(pg_get_serial_sequence('public.categorias', 'id'), (SELECT MAX(id) FROM public.categorias));

-- 7.3 Marcas base
INSERT INTO public.marcas (id, nombre, activo) VALUES
(1, 'Dell Enterprise', TRUE),
(2, 'Cisco Systems', TRUE),
(3, 'Microsoft', TRUE),
(4, 'MikroTik', TRUE),
(5, 'Fortinet', TRUE);
SELECT setval(pg_get_serial_sequence('public.marcas', 'id'), (SELECT MAX(id) FROM public.marcas));

-- 7.4 Estados de factura requeridos por el SRI [1: PENDIENTE, 2: PAGADA, 3: ANULADA]
INSERT INTO public.estados_factura (id, nombre, codigo) VALUES
(1, 'PENDIENTE', 'PENDIENTE'),
(2, 'PAGADA', 'PAGADA'),
(3, 'ANULADA', 'ANULADA');
SELECT setval(pg_get_serial_sequence('public.estados_factura', 'id'), (SELECT MAX(id) FROM public.estados_factura));

-- 7.5 Ciudades base
INSERT INTO public.ciudades (id, nombre, provincia, activo) VALUES
(1, 'Machala', 'El Oro', TRUE),
(2, 'Pasaje', 'El Oro', TRUE),
(3, 'Guayaquil', 'Guayas', TRUE);
SELECT setval(pg_get_serial_sequence('public.ciudades', 'id'), (SELECT MAX(id) FROM public.ciudades));

-- 7.6 Métodos de pago base
INSERT INTO public.metodos_pago (id, nombre, codigo_sri) VALUES
(1, 'Efectivo', '01'),
(2, 'Transferencia Bancaria', '20'),
(3, 'Tarjeta de Crédito / Débito', '19');
SELECT setval(pg_get_serial_sequence('public.metodos_pago', 'id'), (SELECT MAX(id) FROM public.metodos_pago));

-- 7.7 Usuarios iniciales (Administrador, Cliente de prueba y Operador)
INSERT INTO public.usuarios (
    id, usuario, password, email, cedula, nombre, telefono, direccion,
    rol, id_rol, activo, created_by
) VALUES
(
    1,
    'faustoadmin',
    'scrypt:32768:8:1$MfPRitcKzSSCO3jx$f56e9e41884cc72b0137f2314c95424d97686cb798aaeaa8aca31040fe13b4993aec0bbd09faad47b8e1dd5d4efa63568e1c41fed488eaaa0bdae3289b1b74cf',
    'admin@techmanager.com',
    '0700000001',
    'Fausto Administrador',
    '0990001111',
    'Av. 25 de Junio y Rocafuerte, Machala',
    'admin',
    1,
    TRUE,
    'sistema'
),
(
    2,
    'cliente_demo',
    'scrypt:32768:8:1$5p6lMK2YPhCTOi1n$ee443f69367e90721e2fa09b54da501e608b2fc65f18398f8981d02b8a11fe8b5529761515ebc63db07a180363933e186e10889df8b0cf77a49f928982ad3c14',
    'cliente@techmanager.com',
    '0704982134001',
    'Carlos Mendoza Cliente',
    '0987654321',
    'Av. Las Palmeras y Circunvalación Norte, Machala',
    'cliente',
    2,
    TRUE,
    'sistema'
),
(
    3,
    'operador1',
    'scrypt:32768:8:1$5p6lMK2YPhCTOi1n$ee443f69367e90721e2fa09b54da501e608b2fc65f18398f8981d02b8a11fe8b5529761515ebc63db07a180363933e186e10889df8b0cf77a49f928982ad3c14',
    'operador@techmanager.com',
    '0700000002',
    'Operador Principal',
    '0990002222',
    'Av. Las Palmeras, Machala',
    'operador',
    3,
    TRUE,
    'sistema'
);
SELECT setval(pg_get_serial_sequence('public.usuarios', 'id'), (SELECT MAX(id) FROM public.usuarios));

-- 7.8 Clientes iniciales
INSERT INTO public.clientes (
    id, nombres, apellidos, nombre, cedula_ruc, ruc,
    direccion, telefono, email, id_ciudad, usuario_id, activo, created_by
) VALUES
(1, 'Corporación', 'El Rosado S.A.', 'Corporación El Rosado', '0990004199001', '0990004199001', 'Av. 9 de Octubre, Guayaquil', '042598000', 'compras@elrosado.com', 3, NULL, TRUE, 'faustoadmin'),
(2, 'Importadora', 'Tomala S.A.', 'Importadora Tomala S.A.', '0791728394001', '0791728394001', 'Av. Bolívar Madero Vargas, Machala', '072930111', 'contacto@tomala.ec', 1, NULL, TRUE, 'faustoadmin'),
(3, 'Carlos', 'Mendoza', 'Soluciones Informáticas Machala', '0704982134001', '0704982134001', 'Av. Las Palmeras, Machala', '0987654321', 'cliente@techmanager.com', 1, 2, TRUE, 'faustoadmin');
SELECT setval(pg_get_serial_sequence('public.clientes', 'id'), (SELECT MAX(id) FROM public.clientes));

-- 7.9 Proveedores iniciales
INSERT INTO public.proveedores (
    id, razon_social, nombre, ruc, contacto, direccion,
    telefono, email, id_categoria, id_ciudad, activo, created_by
) VALUES
(1, 'TechData Solutions Ecuador S.A.', 'TechData Solutions Ecuador', '0992345678001', 'Ing. Marcos Vivanco', 'Parque Empresarial Colón, Guayaquil', '0998877665', 'ventas@techdata.ec', 1, 3, TRUE, 'faustoadmin'),
(2, 'Cisco Distribution Partner Ecuador', 'Cisco Distribution Partner', '0998765432001', 'Lic. Valeria Castro', 'Av. Francisco de Orellana, Guayaquil', '0983344556', 'canales@ciscopartner.ec', 3, 3, TRUE, 'faustoadmin'),
(3, 'Software & Cloud Solutions Cía. Ltda.', 'Software & Cloud Solutions', '0790011223001', 'Ing. David Salinas', 'Av. 25 de Junio, Machala', '0971239874', 'soporte@softcloud.ec', 2, 1, TRUE, 'faustoadmin');
SELECT setval(pg_get_serial_sequence('public.proveedores', 'id'), (SELECT MAX(id) FROM public.proveedores));

-- 7.10 Productos base iniciales con stock y activo = TRUE
INSERT INTO public.productos (
    id, nombre, descripcion, precio, stock, imagen,
    id_categoria, id_marca, activo, created_by
) VALUES
(1, 'Servidor Dell PowerEdge R450 16GB RAM', 'Servidor empresarial en rack 1U con procesador Intel Xeon Silver y fuente redundante.', 2450.00, 6, 'default_producto.png', 1, 1, TRUE, 'faustoadmin'),
(2, 'Switch Cisco Catalyst 24 Puertos Gigabit', 'Switch administrable Capa 2/3 para redes corporativas de alto tráfico.', 680.00, 14, 'default_producto.png', 3, 2, TRUE, 'faustoadmin'),
(3, 'Router MikroTik CCR2004-16G-2S+', 'Router Cloud Core de borde con 16 puertos Gigabit Ethernet y 2 jaulas SFP+ 10G.', 420.00, 10, 'default_producto.png', 3, 4, TRUE, 'faustoadmin'),
(4, 'Licencia Microsoft Windows Server 2022', 'Licencia perpetua Standard Edition para 16 núcleos físicos y entornos virtualizados.', 890.00, 20, 'default_producto.png', 2, 3, TRUE, 'faustoadmin'),
(5, 'Firewall Fortinet FortiGate 40F', 'Appliance de seguridad perimetral NGFW con SD-WAN integrado y protección avanzada.', 750.00, 8, 'default_producto.png', 4, 5, TRUE, 'faustoadmin');
SELECT setval(pg_get_serial_sequence('public.productos', 'id'), (SELECT MAX(id) FROM public.productos));

-- 7.11 Facturas iniciales
INSERT INTO public.facturas (
    id, numero, fecha, id_cliente, id_usuario,
    subtotal_15, subtotal_0, iva, total, monto,
    id_estado, id_metodo_pago, forma_pago, activo, observacion_anulacion, created_by
) VALUES
(1, 'FAC-2026-001', CURRENT_DATE - INTERVAL '2 days', 1, 1, 2130.43, 0.00, 319.57, 2450.00, 2450.00, 2, 2, 'TRANSFERENCIA BANCARIA', TRUE, NULL, 'faustoadmin'),
(2, 'FAC-2026-002', CURRENT_DATE - INTERVAL '1 day', 2, 1, 956.52, 0.00, 143.48, 1100.00, 1100.00, 2, 1, 'EFECTIVO', TRUE, NULL, 'faustoadmin'),
(3, 'FAC-2026-003', CURRENT_DATE, 3, 1, 652.17, 0.00, 97.83, 750.00, 750.00, 3, 3, 'TARJETA DE CRÉDITO / DÉBITO', TRUE, 'Comprobante anulado por reverso de orden', 'faustoadmin');
SELECT setval(pg_get_serial_sequence('public.facturas', 'id'), (SELECT MAX(id) FROM public.facturas));

-- 7.12 Detalle de facturas iniciales
INSERT INTO public.detalle_facturas (
    id_factura, id_producto, cantidad, precio_unitario, subtotal, iva, total
) VALUES
(1, 1, 1, 2130.43, 2130.43, 319.57, 2450.00),
(2, 3, 1, 365.22, 365.22, 54.78, 420.00),
(2, 2, 1, 591.30, 591.30, 88.70, 680.00),
(3, 5, 1, 652.17, 652.17, 97.83, 750.00);
SELECT setval(pg_get_serial_sequence('public.detalle_facturas', 'id'), (SELECT MAX(id) FROM public.detalle_facturas));

SET LOCAL app.seed_mode = 'off';

-- ==============================================================================
-- PASO 8: CONFIRMACIÓN DE TRANSACCIÓN
-- ==============================================================================

COMMIT;
