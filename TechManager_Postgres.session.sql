SELECT 
    u.id AS usuario_id,
    u.usuario,
    u.email AS email_usuario,
    u.rol,
    c.id AS cliente_id,
    c.nombre AS nombre_cliente,
    c.ruc,
    c.telefono
FROM usuarios u
INNER JOIN clientes c ON c.usuario_id = u.id
WHERE u.usuario = 'Juan Perez' OR c.ruc = '0709876541';