import math


class Paginacion:
    """
    Clase utilitaria reutilizable para estandarizar la paginación SQL y la
    generación de controles de navegación en Jinja2 / Bootstrap 5.
    """

    def __init__(self, items, total_registros, pagina_actual=1, por_pagina=10):
        self.items = list(items) if items is not None else []
        self.total_registros = max(0, int(total_registros or 0))
        self.por_pagina = max(1, int(por_pagina or 10))
        self.pagina_actual = max(1, int(pagina_actual or 1))

    @property
    def total_paginas(self):
        """Número total de páginas (mínimo 1 para consistencia visual)."""
        if self.total_registros == 0:
            return 1
        return math.ceil(self.total_registros / self.por_pagina)

    @property
    def tiene_anterior(self):
        """Indica si existe una página previa a la actual."""
        return self.pagina_actual > 1

    @property
    def tiene_siguiente(self):
        """Indica si existe una página posterior a la actual."""
        return self.pagina_actual < self.total_paginas

    @property
    def pagina_anterior(self):
        """Retorna el número de la página anterior (o None si no aplica)."""
        return self.pagina_actual - 1 if self.tiene_anterior else None

    @property
    def pagina_siguiente(self):
        """Retorna el número de la página siguiente (o None si no aplica)."""
        return self.pagina_actual + 1 if self.tiene_siguiente else None

    @property
    def offset(self):
        """Desplazamiento (OFFSET) calculado para la consulta SQL."""
        return (self.pagina_actual - 1) * self.por_pagina

    @property
    def registro_inicial(self):
        """Índice humano (base 1) del primer registro mostrado en la página."""
        if self.total_registros == 0 or not self.items:
            return 0
        return self.offset + 1

    @property
    def registro_final(self):
        """Índice humano (base 1) del último registro mostrado en la página."""
        if self.total_registros == 0 or not self.items:
            return 0
        return min(self.offset + len(self.items), self.total_registros)

    def rango_paginas(self, margen=2):
        """
        Genera una lista de páginas con ventana deslizante alrededor de
        `pagina_actual`, insertando `None` para representar puntos suspensivos (...).
        Ejemplo: [1, None, 4, 5, 6, None, 20]
        """
        total = self.total_paginas
        actual = self.pagina_actual
        margen = max(1, int(margen))

        if total <= (2 * margen + 5):
            return list(range(1, total + 1))

        paginas = []
        inicio_ventana = max(2, actual - margen)
        fin_ventana = min(total - 1, actual + margen)

        # Siempre incluir la primera página
        paginas.append(1)

        # Puntos suspensivos izquierdos
        if inicio_ventana > 2:
            paginas.append(None)

        # Ventana central
        for num in range(inicio_ventana, fin_ventana + 1):
            paginas.append(num)

        # Puntos suspensivos derechos
        if fin_ventana < total - 1:
            paginas.append(None)

        # Siempre incluir la última página
        if total > 1:
            paginas.append(total)

        return paginas

