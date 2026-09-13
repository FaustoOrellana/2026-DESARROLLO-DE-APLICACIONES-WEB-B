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

CREATE TABLE ciudades (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    CONSTRAINT uq_ciudad_provincia UNIQUE (nombre, provincia)
);

CREATE TABLE categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE marcas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE estados_factura (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE metodos_pago (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    ruc VARCHAR(13) NOT NULL UNIQUE,
    telefono VARCHAR(20) NOT NULL,
    email VARCHAR(120) NOT NULL,
    id_ciudad INT DEFAULT 1,
    CONSTRAINT fk_cliente_ciudad FOREIGN KEY (id_ciudad) REFERENCES ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE proveedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    contacto VARCHAR(150) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    id_categoria INT NOT NULL,
    id_ciudad INT DEFAULT 1,
    CONSTRAINT fk_proveedor_categoria FOREIGN KEY (id_categoria) REFERENCES categorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_proveedor_ciudad FOREIGN KEY (id_ciudad) REFERENCES ciudades(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    precio NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    id_categoria INT NOT NULL,
    id_marca INT DEFAULT 1,
    CONSTRAINT fk_producto_categoria FOREIGN KEY (id_categoria) REFERENCES categorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_producto_marca FOREIGN KEY (id_marca) REFERENCES marcas(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE facturas (
    id SERIAL PRIMARY KEY,
    numero VARCHAR(30) NOT NULL UNIQUE,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    monto NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (monto >= 0),
    id_cliente INT NOT NULL,
    id_estado INT NOT NULL DEFAULT 1,
    id_metodo_pago INT DEFAULT 1,
    CONSTRAINT fk_factura_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_factura_estado FOREIGN KEY (id_estado) REFERENCES estados_factura(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_factura_metodo FOREIGN KEY (id_metodo_pago) REFERENCES metodos_pago(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE detalle_facturas (
    id_factura INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    PRIMARY KEY (id_factura, id_producto),
    CONSTRAINT fk_detalle_factura FOREIGN KEY (id_factura) REFERENCES facturas(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto) REFERENCES productos(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 1. Ciudades
INSERT INTO ciudades (nombre, provincia) VALUES
('Machala', 'El Oro'),
('Pasaje', 'El Oro'),
('Guayaquil', 'Guayas');

-- 2. Categorías
INSERT INTO categorias (nombre, descripcion) VALUES
('Hardware', 'Servidores, estaciones de trabajo, periféricos y equipamiento físico'),
('Software', 'Sistemas operativos corporativos, suites de gestión y aplicativos'),
('Redes', 'Switches administrables, routers de borde, cableado y access points'),
('Licencias', 'Subscripciones de seguridad perimetral, bases de datos y software empresarial');

-- 3. Marcas
INSERT INTO marcas (nombre) VALUES
('Dell Enterprise'),
('Cisco Systems'),
('Microsoft'),
('MikroTik'),
('Fortinet');

-- 4. Estados de Factura
INSERT INTO estados_factura (nombre) VALUES
('Pagada'),
('Pendiente'),
('Anulada');

-- 5. Métodos de Pago
INSERT INTO metodos_pago (nombre) VALUES
('Transferencia Bancaria'),
('Tarjeta de Crédito Corporativa'),
('Efectivo');

-- 6. Clientes
INSERT INTO clientes (nombre, ruc, telefono, email, id_ciudad) VALUES
('Banco de Machala S.A.', '0790012345001', '072930100', 'soporte.ti@bancomachala.com', 1),
('Corporación Telecom del Sur', '0791745829001', '0981122334', 'infraestructura@telecomsur.ec', 1),
('Colegio de Ingenieros de El Oro', '0791827364001', '072984512', 'administracion@cipo.org.ec', 2);

-- 7. Proveedores
INSERT INTO proveedores (nombre, contacto, telefono, id_categoria, id_ciudad) VALUES
('TechData Solutions Ecuador', 'Ing. Marcos Vivanco', '0998877665', 1, 3),
('Cisco Distribution Partner', 'Lic. Valeria Castro', '0983344556', 3, 3),
('Software & Cloud Solutions', 'Ing. David Salinas', '0971239874', 2, 1);

-- 8. Productos
INSERT INTO productos (nombre, precio, stock, id_categoria, id_marca) VALUES
('Servidor Dell PowerEdge R450 16GB RAM', 2450.00, 6, 1, 1),
('Switch Cisco Catalyst 24 Puertos Gigabit', 680.00, 14, 3, 2),
('Router MikroTik CCR2004-16G-2S+', 420.00, 10, 3, 4),
('Licencia Microsoft Windows Server 2022', 890.00, 20, 2, 3),
('Firewall Fortinet FortiGate 40F', 750.00, 8, 4, 5);

-- 9. Facturas
INSERT INTO facturas (numero, fecha, monto, id_cliente, id_estado, id_metodo_pago) VALUES
('FAC-2026-001', '2026-09-08', 3130.00, 1, 1, 1),
('FAC-2026-002', '2026-09-09', 1100.00, 2, 2, 1);

-- 10. Detalle de Facturas
INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario) VALUES
(1, 1, 1, 2450.00),
(1, 2, 1, 680.00);

INSERT INTO detalle_facturas (id_factura, id_producto, cantidad, precio_unitario) VALUES
(2, 3, 1, 420.00),
(2, 2, 1, 680.00);