-- PROYECTO INTEGRADOR: TECHMANAGER SYSTEM
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

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'usuario',
    intentos_fallidos INT DEFAULT 0,
    bloqueado_hasta TIMESTAMP NULL
);

-- Catálogo de Ciudades
CREATE TABLE ciudades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    CONSTRAINT uq_ciudad_provincia UNIQUE (nombre, provincia)
);

-- Catálogo de Categorías
CREATE TABLE categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);

-- Catálogo de Marcas
CREATE TABLE marcas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Estados de Factura
CREATE TABLE estados_factura (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

-- Métodos de Pago
CREATE TABLE metodos_pago (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

-- Directorio de Clientes
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    ruc VARCHAR(13) NOT NULL UNIQUE,
    telefono VARCHAR(20) NOT NULL,
    email VARCHAR(120) NOT NULL,
    id_ciudad INT DEFAULT 1,
    usuario_id INT NULL,
    CONSTRAINT fk_cliente_ciudad FOREIGN KEY (id_ciudad) 
        REFERENCES ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cliente_usuario FOREIGN KEY (usuario_id) 
        REFERENCES usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL
);

-- Directorio de Proveedores
CREATE TABLE proveedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    contacto VARCHAR(150) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    id_categoria INT NOT NULL,
    id_ciudad INT DEFAULT 1,
    CONSTRAINT fk_proveedor_categoria FOREIGN KEY (id_categoria) 
        REFERENCES categorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_proveedor_ciudad FOREIGN KEY (id_ciudad) 
        REFERENCES ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Inventario de Productos
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    precio NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    id_categoria INT NOT NULL,
    id_marca INT DEFAULT 1,
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
    PRIMARY KEY (id_factura, id_producto),
    CONSTRAINT fk_detalle_factura FOREIGN KEY (id_factura) 
        REFERENCES facturas(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto) 
        REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Inserción de Catálogos Base
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

-- Inserción de Usuarios Administrativos
INSERT INTO usuarios (usuario, email, password, rol, intentos_fallidos, bloqueado_hasta) VALUES
('faustoadmin', 'admin@techmanager.com', 'scrypt:32768:8:1$MfPRitcKzSSCO3jx$f56e9e41884cc72b0137f2314c95424d97686cb798aaeaa8aca31040fe13b4993aec0bbd09faad47b8e1dd5d4efa63568e1c41fed488eaaa0bdae3289b1b74cf', 'admin', 0, NULL),
('operador1', 'operador@techmanager.com', 'scrypt:32768:8:1$5p6lMK2YPhCTOi1n$ee443f69367e90721e2fa09b54da501e608b2fc65f18398f8981d02b8a11fe8b5529761515ebc63db07a180363933e186e10889df8b0cf77a49f928982ad3c14', 'operador', 0, NULL);

-- Inserción de Proveedores
INSERT INTO proveedores (nombre, contacto, telefono, id_categoria, id_ciudad) VALUES
('TechData Solutions Ecuador', 'Ing. Marcos Vivanco', '0998877665', 1, 3),
('Cisco Distribution Partner', 'Lic. Valeria Castro', '0983344556', 3, 3),
('Software & Cloud Solutions', 'Ing. David Salinas', '0971239874', 2, 1);

-- Inserción de Productos
INSERT INTO productos (nombre, precio, stock, id_categoria, id_marca) VALUES
('Servidor Dell PowerEdge R450 16GB RAM', 2450.00, 6, 1, 1),
('Switch Cisco Catalyst 24 Puertos Gigabit', 680.00, 14, 3, 2),
('Router MikroTik CCR2004-16G-2S+', 420.00, 10, 3, 4),
('Licencia Microsoft Windows Server 2022', 890.00, 20, 2, 3),
('Firewall Fortinet FortiGate 40F', 750.00, 8, 4, 5);

-- Inserción de Clientes
INSERT INTO clientes (nombre, ruc, telefono, email, id_ciudad, usuario_id) VALUES
('Corporación El Rosado', '0990004199001', '042598000', 'compras@elrosado.com', 3, NULL),
('Importadora Tomala S.A.', '0791728394001', '072930111', 'contacto@tomala.ec', 1, NULL),
('Soluciones Informáticas Machala', '0704982134001', '0987654321', 'info@simachala.com', 1, NULL);

-- Inserción de Facturas Iniciales (Formato Estándar Correlativo FAC-YYYY-XXX)
INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago) VALUES
('FAC-2026-001', CURRENT_DATE - INTERVAL '2 days', 2450.00, 1, 1, 2),
('FAC-2026-002', CURRENT_DATE - INTERVAL '1 day', 1100.00, 2, 1, 1),
('FAC-2026-003', CURRENT_DATE, 750.00, 3, 2, 3);

-- Inserción de Detalle de Facturas
INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario) VALUES
(1, 1, 1, 2450.00),
(2, 3, 1, 420.00),
(2, 2, 1, 680.00),
(3, 5, 1, 750.00);