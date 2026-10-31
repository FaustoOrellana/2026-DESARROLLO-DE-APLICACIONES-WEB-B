-- ==============================================================================
-- PROYECTO INTEGRADOR: TECHMANAGER SYSTEM (v2.0.0)
-- ESQUEMA COMPLETO ALINEADO CON app.py (SOFT DELETE, AUDITORÍA Y TRIGGERS)
-- ==============================================================================

-- 1. LIMPIEZA DE OBJETOS EXISTENTES (EN ORDEN INVERSO DE DEPENDENCIAS)
DROP TRIGGER IF EXISTS trg_descontar_stock_detalle ON detalle_facturas;
DROP FUNCTION IF EXISTS fn_descontar_stock_detalle() CASCADE;

DROP TRIGGER IF EXISTS trg_auditoria_usuarios ON usuarios;
DROP TRIGGER IF EXISTS trg_auditoria_clientes ON clientes;
DROP TRIGGER IF EXISTS trg_auditoria_proveedores ON proveedores;
DROP TRIGGER IF EXISTS trg_auditoria_productos ON productos;
DROP TRIGGER IF EXISTS trg_auditoria_facturas ON facturas;
DROP FUNCTION IF EXISTS fn_registrar_auditoria() CASCADE;

DROP TABLE IF EXISTS auditoria CASCADE;
DROP TABLE IF EXISTS detalle_facturas CASCADE;
DROP TABLE IF EXISTS facturas CASCADE;
DROP TABLE IF EXISTS productos CASCADE;
DROP TABLE IF EXISTS proveedores CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;
DROP TABLE IF EXISTS metodos_pago CASCADE;
DROP TABLE IF EXISTS estados_factura CASCADE;
DROP TABLE IF EXISTS marcas CASCADE;
DROP TABLE IF EXISTS categorias CASCADE;
DROP TABLE IF EXISTS ciudades CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;

-- ==============================================================================
-- 2. CREACIÓN DE TABLAS DE CATÁLOGO Y SEGURIDAD
-- ==============================================================================

-- Tabla de Usuarios del Sistema
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(150) NULL,
    cedula VARCHAR(13) UNIQUE NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    telefono VARCHAR(20) NULL,
    direccion TEXT NULL,
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'usuario',
    intentos_fallidos INT DEFAULT 0,
    bloqueado_hasta TIMESTAMP NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(50) DEFAULT 'system',
    modified_by VARCHAR(50) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Catálogo de Ciudades
CREATE TABLE ciudades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_ciudad_provincia UNIQUE (nombre, provincia)
);

-- Catálogo de Categorías
CREATE TABLE categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

-- Catálogo de Marcas
CREATE TABLE marcas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

-- Estados de Factura (1: Pagada, 2: Pendiente, 3: Anulada)
CREATE TABLE estados_factura (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

-- Métodos de Pago (1: Efectivo, 2: Transferencia Bancaria, 3: Tarjeta de Crédito / Débito)
CREATE TABLE metodos_pago (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

-- ==============================================================================
-- 3. CREACIÓN DE TABLAS OPERATIVAS PRINCIPALES (CON AUDITORÍA Y SOFT DELETE)
-- ==============================================================================

-- Directorio de Clientes
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    ruc VARCHAR(13) UNIQUE NULL,
    telefono VARCHAR(20) NOT NULL,
    email VARCHAR(120) NOT NULL,
    id_ciudad INT DEFAULT 1,
    usuario_id INT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(50) DEFAULT 'system',
    modified_by VARCHAR(50) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cliente_ciudad FOREIGN KEY (id_ciudad) 
        REFERENCES ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cliente_usuario FOREIGN KEY (usuario_id) 
        REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- Directorio de Proveedores
CREATE TABLE proveedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    contacto VARCHAR(150) NULL,
    telefono VARCHAR(20) NOT NULL,
    id_categoria INT NOT NULL,
    id_ciudad INT DEFAULT 1,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(50) DEFAULT 'system',
    modified_by VARCHAR(50) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_proveedor_categoria FOREIGN KEY (id_categoria) 
        REFERENCES categorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_proveedor_ciudad FOREIGN KEY (id_ciudad) 
        REFERENCES ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Inventario de Productos
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    precio NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    id_categoria INT NOT NULL,
    id_marca INT DEFAULT 1,
    imagen VARCHAR(255) NOT NULL DEFAULT 'default_producto.png',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(50) DEFAULT 'system',
    modified_by VARCHAR(50) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_producto_categoria FOREIGN KEY (id_categoria) 
        REFERENCES categorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_producto_marca FOREIGN KEY (id_marca) 
        REFERENCES marcas(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Cabecera de Facturación
CREATE TABLE facturas (
    id SERIAL PRIMARY KEY,
    numero VARCHAR(30) NOT NULL UNIQUE,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    monto NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (monto >= 0),
    id_cliente INT NOT NULL,
    id_estado INT NOT NULL DEFAULT 1,
    id_metodo_pago INT DEFAULT 1,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(50) DEFAULT 'system',
    modified_by VARCHAR(50) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_factura_cliente FOREIGN KEY (id_cliente) 
        REFERENCES clientes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_factura_estado FOREIGN KEY (id_estado) 
        REFERENCES estados_factura(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_factura_metodo FOREIGN KEY (id_metodo_pago) 
        REFERENCES metodos_pago(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Detalle de Factura
CREATE TABLE detalle_facturas (
    id_factura INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal >= 0),
    PRIMARY KEY (id_factura, id_producto),
    CONSTRAINT fk_detalle_factura FOREIGN KEY (id_factura) 
        REFERENCES facturas(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto) 
        REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Tabla Centralizada de Auditoría
CREATE TABLE auditoria (
    id_auditoria SERIAL PRIMARY KEY,
    tabla_afectada VARCHAR(50) NOT NULL,
    id_registro INT NOT NULL,
    operacion VARCHAR(20) NOT NULL, -- 'INSERT', 'UPDATE', 'SOFT_DELETE', 'DELETE'
    usuario VARCHAR(50) DEFAULT 'system',
    datos_previos JSONB NULL,
    datos_nuevos JSONB NULL,
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 4. INSERCIÓN DE DATOS SEMILLA (SEED DATA)
-- (Se insertan antes de activar el trigger de stock para conservar el stock base)
-- ==============================================================================

-- Catálogos Base
INSERT INTO ciudades (nombre, provincia) VALUES
('Machala', 'El Oro'),
('Pasaje', 'El Oro'),
('Guayaquil', 'Guayas');

INSERT INTO categorias (nombre, descripcion) VALUES
('Hardware', 'Servidores, estaciones de trabajo, periféricos y equipamiento físico'),
('Software', 'Sistemas operativos corporativos, suites de gestión y aplicativos'),
('Redes', 'Switches administrables, routers de borde, cableado y access points'),
('Licencias', 'Suscripciones de seguridad perimetral, bases de datos y software empresarial');

INSERT INTO marcas (nombre) VALUES
('Dell Enterprise'),
('Cisco Systems'),
('Microsoft'),
('MikroTik'),
('Fortinet');

INSERT INTO estados_factura (nombre) VALUES
('Pagada'),
('Pendiente'),
('Anulada');

INSERT INTO metodos_pago (nombre) VALUES
('Efectivo'),
('Transferencia Bancaria'),
('Tarjeta de Crédito / Débito');

-- Usuarios Administrativos y Operativos
INSERT INTO usuarios (usuario, nombre, cedula, email, telefono, direccion, password, rol, intentos_fallidos, bloqueado_hasta, activo, created_by) VALUES
('faustoadmin', 'Fausto Administrador', '0700000001', 'admin@techmanager.com', '0990001111', 'Av. 25 de Junio y Rocafuerte, Machala', 'scrypt:32768:8:1$MfPRitcKzSSCO3jx$f56e9e41884cc72b0137f2314c95424d97686cb798aaeaa8aca31040fe13b4993aec0bbd09faad47b8e1dd5d4efa63568e1c41fed488eaaa0bdae3289b1b74cf', 'admin', 0, NULL, TRUE, 'system'),
('operador1', 'Operador Principal', '0700000002', 'operador@techmanager.com', '0990002222', 'Av. Las Palmeras, Machala', 'scrypt:32768:8:1$5p6lMK2YPhCTOi1n$ee443f69367e90721e2fa09b54da501e608b2fc65f18398f8981d02b8a11fe8b5529761515ebc63db07a180363933e186e10889df8b0cf77a49f928982ad3c14', 'operador', 0, NULL, TRUE, 'system');

-- Proveedores Iniciales
INSERT INTO proveedores (nombre, contacto, telefono, id_categoria, id_ciudad, activo, created_by) VALUES
('TechData Solutions Ecuador', 'Ing. Marcos Vivanco', '0998877665', 1, 3, TRUE, 'faustoadmin'),
('Cisco Distribution Partner', 'Lic. Valeria Castro', '0983344556', 3, 3, TRUE, 'faustoadmin'),
('Software & Cloud Solutions', 'Ing. David Salinas', '0971239874', 2, 1, TRUE, 'faustoadmin');

-- Productos Iniciales (con descripción y auditoría)
INSERT INTO productos (nombre, descripcion, precio, stock, id_categoria, id_marca, activo, created_by) VALUES
('Servidor Dell PowerEdge R450 16GB RAM', 'Servidor empresarial en rack 1U con procesador Intel Xeon Silver y fuente redundante.', 2450.00, 6, 1, 1, TRUE, 'faustoadmin'),
('Switch Cisco Catalyst 24 Puertos Gigabit', 'Switch administrable Capa 2/3 para redes corporativas de alto tráfico.', 680.00, 14, 3, 2, TRUE, 'faustoadmin'),
('Router MikroTik CCR2004-16G-2S+', 'Router Cloud Core de borde con 16 puertos Gigabit Ethernet y 2 jaulas SFP+ 10G.', 420.00, 10, 3, 4, TRUE, 'faustoadmin'),
('Licencia Microsoft Windows Server 2022', 'Licencia perpetua Standard Edition para 16 núcleos físicos y entornos virtualizados.', 890.00, 20, 2, 3, TRUE, 'faustoadmin'),
('Firewall Fortinet FortiGate 40F', 'Appliance de seguridad perimetral NGFW con SD-WAN integrado y protección avanzada.', 750.00, 8, 4, 5, TRUE, 'faustoadmin');

-- Clientes Iniciales
INSERT INTO clientes (nombre, ruc, telefono, email, id_ciudad, usuario_id, activo, created_by) VALUES
('Corporación El Rosado', '0990004199001', '042598000', 'compras@elrosado.com', 3, NULL, TRUE, 'faustoadmin'),
('Importadora Tomala S.A.', '0791728394001', '072930111', 'contacto@tomala.ec', 1, NULL, TRUE, 'faustoadmin'),
('Soluciones Informáticas Machala', '0704982134001', '0987654321', 'info@simachala.com', 1, NULL, TRUE, 'faustoadmin');

-- Facturas Iniciales (Formato Estándar Correlativo FAC-YYYY-XXX)
INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago, activo, created_by) VALUES
('FAC-2026-001', CURRENT_DATE - INTERVAL '2 days', 2450.00, 1, 1, 2, TRUE, 'faustoadmin'),
('FAC-2026-002', CURRENT_DATE - INTERVAL '1 day', 1100.00, 2, 1, 1, TRUE, 'faustoadmin'),
('FAC-2026-003', CURRENT_DATE, 750.00, 3, 2, 3, TRUE, 'faustoadmin');

-- Detalle de Facturas Iniciales (con subtotal calculado)
INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario, subtotal) VALUES
(1, 1, 1, 2450.00, 2450.00),
(2, 3, 1, 420.00, 420.00),
(2, 2, 1, 680.00, 680.00),
(3, 5, 1, 750.00, 750.00);

-- ==============================================================================
-- 5. FUNCIONES Y TRIGGERS (CONTROL DE INVENTARIO Y AUDITORÍA AUTOMÁTICA)
-- ==============================================================================

-- 5.1 Trigger para autocompletar subtotal y descontar stock al emitir factura
-- NOTA: En app.py (editar_factura) el UPDATE de facturas se ejecuta DESPUÉS de
-- reinsertar detalle_facturas, y editar_factura ya descuenta stock manualmente.
-- Para evitar doble descuento en edición y descontar una única vez en creación
-- (formulario_facturacion y finalizar_compra), verificamos que la factura sea recién
-- creada en la transacción actual (xmin = txid_current()::xid) y no esté anulada.
CREATE OR REPLACE FUNCTION fn_descontar_stock_detalle()
RETURNS TRIGGER AS $$
DECLARE
    v_estado INT;
    v_es_nueva BOOLEAN;
BEGIN
    -- Asegurar cálculo de subtotal si no fue provisto
    IF NEW.subtotal IS NULL OR NEW.subtotal = 0 THEN
        NEW.subtotal := ROUND(NEW.cantidad * NEW.precio_unitario, 2);
    END IF;

    -- Verificar estado de la factura y si fue creada en esta misma transacción
    SELECT id_estado, (xmin::text = (txid_current() % (2^32)::bigint)::text)
    INTO v_estado, v_es_nueva
    FROM facturas
    WHERE id = NEW.id_factura;

    -- Solo descontar automáticamente cuando es una factura nueva (creación o checkout)
    -- y su estado no es Anulada (3)
    IF COALESCE(v_es_nueva, TRUE) AND COALESCE(v_estado, 1) != 3 THEN
        UPDATE productos
        SET stock = stock - NEW.cantidad,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id_producto;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_descontar_stock_detalle
BEFORE INSERT ON detalle_facturas
FOR EACH ROW
EXECUTE FUNCTION fn_descontar_stock_detalle();


-- 5.2 Función y Triggers Globales de Auditoría (INSERT, UPDATE y SOFT_DELETE)
CREATE OR REPLACE FUNCTION fn_registrar_auditoria()
RETURNS TRIGGER AS $$
DECLARE
    v_accion VARCHAR(20);
    v_usuario VARCHAR(50);
    v_registro_id INT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_accion := 'INSERT';
        v_registro_id := NEW.id;
        v_usuario := COALESCE(NEW.created_by, 'system');

        INSERT INTO auditoria (tabla_afectada, id_registro, operacion, usuario, datos_previos, datos_nuevos)
        VALUES (TG_TABLE_NAME, v_registro_id, v_accion, v_usuario, NULL, to_jsonb(NEW));
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        NEW.updated_at := CURRENT_TIMESTAMP;
        v_registro_id := NEW.id;
        v_usuario := COALESCE(NEW.modified_by, NEW.created_by, 'system');

        -- Detectar si fue un borrado lógico (Soft Delete)
        IF OLD.activo IS TRUE AND NEW.activo IS FALSE THEN
            v_accion := 'SOFT_DELETE';
        ELSE
            v_accion := 'UPDATE';
        END IF;

        INSERT INTO auditoria (tabla_afectada, id_registro, operacion, usuario, datos_previos, datos_nuevos)
        VALUES (TG_TABLE_NAME, v_registro_id, v_accion, v_usuario, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        v_accion := 'DELETE';
        v_registro_id := OLD.id;
        v_usuario := COALESCE(OLD.modified_by, OLD.created_by, 'system');

        INSERT INTO auditoria (tabla_afectada, id_registro, operacion, usuario, datos_previos, datos_nuevos)
        VALUES (TG_TABLE_NAME, v_registro_id, v_accion, v_usuario, to_jsonb(OLD), NULL);
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditoria_usuarios
BEFORE INSERT OR UPDATE OR DELETE ON usuarios
FOR EACH ROW EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_clientes
BEFORE INSERT OR UPDATE OR DELETE ON clientes
FOR EACH ROW EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_proveedores
BEFORE INSERT OR UPDATE OR DELETE ON proveedores
FOR EACH ROW EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_productos
BEFORE INSERT OR UPDATE OR DELETE ON productos
FOR EACH ROW EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_facturas
BEFORE INSERT OR UPDATE OR DELETE ON facturas
FOR EACH ROW EXECUTE FUNCTION fn_registrar_auditoria();

