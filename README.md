# TechManager — Enterprise ERP & Facturación Electrónica

[![Status](https://img.shields.io/badge/Status-Production%20Live-brightgreen)](https://two026-desarrollo-de-aplicaciones-web-b.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask%203.x-black.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20(Supabase)-3ECF8E.svg)](https://supabase.com)
[![Deployment](https://img.shields.io/badge/Deployment-Render-46E3B7.svg)](https://render.com)

**TechManager** es una solución web integral de planificación de recursos empresariales (ERP) diseñada para optimizar la gestión comercial, control de inventario en tiempo real, facturación estructurada y trazabilidad operativa bajo estándares de auditoría.

---

## 🚀 Arquitectura y Stack Tecnológico

- **Backend:** Python 3.11 con microframework Flask.
- **Base de Datos:** PostgreSQL 16 alojada en Supabase (Session Pooler IPv4 vía Supavisor).
- **Driver Relacional:** `psycopg2-binary` para ejecución transaccional nativa.
- **Servidor Web / WSGI:** Gunicorn sobre Render Web Services.
- **Seguridad y Control de Acceso:** Autenticación por sesiones con hashing seguro y control de acceso basado en roles (RBAC).
- **Lógica de Base de Datos:** Procedimientos almacenados en PL/pgSQL y disparadores automáticos (`TRIGGERS`) para auditoría de cambios y sincronización de stock.

---

## ⚙️ Características Principales

1. **Gestión de Inventario y Productos:**
   - Control de stock con deducción automática al facturar mediante triggers en base de datos.
   - Categorización jerárquica y parametrización de marcas y márgenes comerciales.

2. **Módulo de Facturación y Ventas:**
   - Emisión y control de estados de facturas.
   - Estructuración de datos compatible con normativa tributaria (cálculo de subtotal, IVA y totales).
   - Generación de comprobantes y reportes comerciales en PDF.

3. **Auditoría Transaccional Integral:**
   - Registro cronológico inmutable de operaciones (`INSERT`, `UPDATE`, `DELETE`) en tabla de auditoría.
   - Trazabilidad de usuario responsable, dirección de red y marca de tiempo.

4. **Administración de Clientes y Proveedores:**
   - Validación de identificaciones (Cédula / RUC).
   - Historial consolidado de compras y cuentas asociadas.

---

## 📋 Variables de Entorno

```env
DATABASE_URL=postgresql://<usuario>:<password>@<host-pooler>:5432/<database>
SECRET_KEY=<clave_secreta_para_sesiones>
PYTHON_VERSION=3.11.9