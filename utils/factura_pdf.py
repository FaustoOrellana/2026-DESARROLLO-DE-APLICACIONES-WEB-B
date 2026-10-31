import io
import os
import re
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


# Datos tributarios oficiales del Emisor (TechManager Solutions)
EMISOR_SRI = {
    "nombre_comercial": "TECHMANAGER SOLUTIONS",
    "razon_social": "TECHMANAGER SOLUTIONS ECUADOR S.A.",
    "ruc": "0701234567001",
    "direccion_matriz": "Av. 25 de Junio y Rocafuerte, Edif. Corporativo Piso 3 - Machala, El Oro",
    "direccion_sucursal": "Av. 25 de Junio y Rocafuerte - Machala, El Oro",
    "obligado_contabilidad": "NO",
    "regimen": "CONTRIBUYENTE RÉGIMEN RIMPE",
    "ambiente": "PRODUCCIÓN",
    "emision": "NORMAL"
}


def formatear_numero_sri(numero_raw, id_factura=1):
    """
    Convierte el número interno de factura (ej. 'FAC-2026-003' o '123')
    al formato secuencial oficial del SRI: '001-001-000000123' (9 dígitos).
    """
    if numero_raw:
        cadena = str(numero_raw).strip()
        if re.match(r'^\d{3}-\d{3}-\d{9}$', cadena):
            return cadena
        digitos_finales = re.findall(r'(\d+)$', cadena)
        if digitos_finales:
            secuencial = int(digitos_finales[-1])
            return f"001-001-{secuencial:09d}"
    return f"001-001-{int(id_factura or 1):09d}"


def calcular_digito_modulo11(cadena_48):
    """Calcula el dígito verificador Módulo 11 oficial del SRI para la clave de acceso de 49 dígitos."""
    factores = [2, 3, 4, 5, 6, 7]
    suma = 0
    indice_factor = 0
    for digito in reversed(cadena_48):
        suma += int(digito) * factores[indice_factor]
        indice_factor = (indice_factor + 1) % 6
    residuo = 11 - (suma % 11)
    if residuo == 11:
        return 0
    if residuo == 10:
        return 1
    return residuo


def generar_clave_acceso_sri(fecha_emision, ruc_emisor, numero_sri, id_factura=1):
    """
    Genera una Clave de Acceso / Número de Autorización de 49 dígitos numéricos
    conforme a la ficha técnica de Comprobantes Electrónicos del SRI:
      - Fecha de emisión (ddmmaaaa): 8 dígitos
      - Tipo de comprobante (01 = Factura): 2 dígitos
      - RUC del emisor: 13 dígitos
      - Tipo de ambiente (2 = Producción): 1 dígito
      - Serie (001001): 6 dígitos
      - Secuencial (9 dígitos): 9 dígitos
      - Código numérico interno (8 dígitos): 8 dígitos
      - Tipo de emisión (1 = Normal): 1 dígito
      - Dígito verificador (Módulo 11): 1 dígito
    """
    if hasattr(fecha_emision, 'strftime'):
        fecha_8 = fecha_emision.strftime('%d%m%Y')
    else:
        try:
            dt = datetime.strptime(str(fecha_emision)[:10], '%Y-%m-%d')
            fecha_8 = dt.strftime('%d%m%Y')
        except Exception:
            fecha_8 = datetime.now().strftime('%d%m%Y')

    tipo_comp = "01"
    ruc_13 = re.sub(r'\D', '', str(ruc_emisor))[:13].ljust(13, '0')
    ambiente_1 = "2"

    partes_serie = str(numero_sri).split('-')
    if len(partes_serie) == 3:
        serie_6 = f"{partes_serie[0]}{partes_serie[1]}"
        secuencial_9 = partes_serie[2].zfill(9)
    else:
        serie_6 = "001001"
        secuencial_9 = f"{int(id_factura or 1):09d}"

    codigo_numerico_8 = f"{(int(id_factura or 1) * 12345) % 100000000:08d}"
    tipo_emision_1 = "1"

    base_48 = f"{fecha_8}{tipo_comp}{ruc_13}{ambiente_1}{serie_6}{secuencial_9}{codigo_numerico_8}{tipo_emision_1}"
    base_48 = re.sub(r'\D', '0', base_48)[:48].ljust(48, '0')
    digito_verificador = calcular_digito_modulo11(base_48)
    return f"{base_48}{digito_verificador}"


def mapear_forma_pago_sri(metodo_nombre):
    """Mapea el método de pago interno al catálogo oficial de Formas de Pago del SRI."""
    texto = str(metodo_nombre or '').lower()
    if 'tarjeta' in texto and 'crédito' in texto:
        return "19 - TARJETA DE CRÉDITO"
    if 'tarjeta' in texto and 'débito' in texto:
        return "16 - TARJETA DE DÉBITO"
    if 'tarjeta' in texto:
        return "19 - TARJETA DE CRÉDITO / DÉBITO"
    if 'transferencia' in texto or 'banc' in texto or 'financiero' in texto:
        return "20 - OTROS CON UTILIZACIÓN DEL SISTEMA FINANCIERO"
    return "01 - SIN UTILIZACIÓN DEL SISTEMA FINANCIERO"


def obtener_elemento_logo_ride(ancho_max_pt=145, alto_max_pt=58):
    """
    Localiza exclusivamente el archivo 'TechManager_Emblem.png' dentro de
    'static/img/' o 'static/images/' validando con os.path.exists(). Si existe,
    retorna una instancia de reportlab.platypus.Image escalada proporcionalmente
    (manteniendo relación de aspecto y alineación izquierda); de lo contrario
    retorna None para usar el texto de respaldo.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    rutas_candidatas = [
        os.path.join(base_dir, 'static', 'img', 'TechManager_Emblem.png'),
        os.path.join(base_dir, 'static', 'images', 'TechManager_Emblem.png'),
    ]

    for ruta_logo in rutas_candidatas:
        if os.path.exists(ruta_logo) and os.path.isfile(ruta_logo):
            try:
                lector = ImageReader(ruta_logo)
                ancho_orig, alto_orig = lector.getSize()
                if ancho_orig > 0 and alto_orig > 0:
                    ratio = float(alto_orig) / float(ancho_orig)
                    ancho_final = float(ancho_max_pt)
                    alto_final = ancho_final * ratio
                    if alto_final > alto_max_pt:
                        alto_final = float(alto_max_pt)
                        ancho_final = alto_final / ratio
                else:
                    ancho_final = float(ancho_max_pt)
                    alto_final = 45.0

                logo_img = Image(ruta_logo, width=ancho_final, height=alto_final)
                logo_img.hAlign = 'LEFT'
                return logo_img
            except Exception:
                continue

    return None


def generar_pdf_ride_sri(factura, detalles):
    """
    Construye en memoria (io.BytesIO) el PDF del RIDE (Representación Impresa de
    Comprobante Electrónico) cumpliendo con la estructura tributaria del SRI (Ecuador).
    Retorna: (buffer_pdf, numero_sri)
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"RIDE Factura {factura.get('numero', '')}"
    )

    ancho_util = letter[0] - (3.0 * cm)  # ~18.59 cm
    styles = getSampleStyleSheet()

    # Estilos tipográficos personalizados
    style_emisor_titulo = ParagraphStyle(
        'EmisorTitulo',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#0f172a')
    )
    style_normal = ParagraphStyle(
        'RideNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#1e293b')
    )
    style_bold = ParagraphStyle(
        'RideBold',
        parent=style_normal,
        fontName='Helvetica-Bold'
    )
    style_small = ParagraphStyle(
        'RideSmall',
        parent=style_normal,
        fontSize=7.5,
        leading=10
    )
    style_clave = ParagraphStyle(
        'RideClave',
        parent=style_normal,
        fontName='Courier-Bold',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor('#0f172a')
    )
    style_th = ParagraphStyle(
        'RideTableHeader',
        parent=style_bold,
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1
    )
    style_td_center = ParagraphStyle(
        'RideTdCenter',
        parent=style_normal,
        fontSize=8,
        alignment=1
    )
    style_td_right = ParagraphStyle(
        'RideTdRight',
        parent=style_normal,
        fontSize=8,
        alignment=2
    )

    id_fac = factura.get('id', 1)
    numero_sri = formatear_numero_sri(factura.get('numero'), id_fac)
    fecha_raw = factura.get('fecha')
    if hasattr(fecha_raw, 'strftime'):
        fecha_emision_str = fecha_raw.strftime('%d/%m/%Y') + " " + datetime.now().strftime('%H:%M')
    else:
        try:
            dt = datetime.strptime(str(fecha_raw)[:10], '%Y-%m-%d')
            fecha_emision_str = dt.strftime('%d/%m/%Y') + " 10:30"
        except Exception:
            fecha_emision_str = str(fecha_raw or datetime.now().strftime('%d/%m/%Y %H:%M'))

    clave_acceso = generar_clave_acceso_sri(
        fecha_raw,
        EMISOR_SRI['ruc'],
        numero_sri,
        id_fac
    )

    elementos = []

    # ==========================================================================
    # 1. ENCABEZADO DIVIDIDO EN DOS COLUMNAS (TABLA 2x1: EMISOR | TRIBUTARIO)
    # ==========================================================================
    col_izquierda = []
    logo_flowable = obtener_elemento_logo_ride(ancho_max_pt=150, alto_max_pt=56)
    if logo_flowable is not None:
        col_izquierda.append(logo_flowable)
        col_izquierda.append(Spacer(1, 5))

    col_izquierda.extend([
        Paragraph(EMISOR_SRI['nombre_comercial'], style_emisor_titulo),
        Spacer(1, 4),
        Paragraph(f"<b>Razón Social:</b> {EMISOR_SRI['razon_social']}", style_normal),
        Paragraph(f"<b>RUC:</b> {EMISOR_SRI['ruc']}", style_normal),
        Paragraph(f"<b>Dirección Matriz:</b> {EMISOR_SRI['direccion_matriz']}", style_normal),
        Paragraph(f"<b>Dirección Sucursal:</b> {EMISOR_SRI['direccion_sucursal']}", style_normal),
        Spacer(1, 3),
        Paragraph(f"<b>OBLIGADO A LLEVAR CONTABILIDAD:</b> {EMISOR_SRI['obligado_contabilidad']}", style_normal),
        Paragraph(f"<b>{EMISOR_SRI['regimen']}</b>", style_bold)
    ])

    col_derecha = [
        Paragraph(f"<b>R.U.C.:</b> {EMISOR_SRI['ruc']}", style_bold),
        Spacer(1, 2),
        Paragraph("<font size=11 color='#1d4ed8'><b>FACTURA</b></font>", style_bold),
        Paragraph(f"<b>No.</b> <font color='#dc2626'>{numero_sri}</font>", style_bold),
        Spacer(1, 3),
        Paragraph("<b>NÚMERO DE AUTORIZACIÓN:</b>", style_small),
        Paragraph(clave_acceso, style_clave),
        Spacer(1, 2),
        Paragraph(f"<b>FECHA Y HORA DE AUTORIZACIÓN:</b> {fecha_emision_str}", style_small),
        Paragraph(f"<b>AMBIENTE:</b> {EMISOR_SRI['ambiente']}", style_normal),
        Paragraph(f"<b>EMISIÓN:</b> {EMISOR_SRI['emision']}", style_normal),
        Spacer(1, 2),
        Paragraph("<b>CLAVE DE ACCESO:</b>", style_small),
        Paragraph(clave_acceso, style_clave)
    ]

    tabla_encabezado = Table(
        [[col_izquierda, col_derecha]],
        colWidths=[ancho_util * 0.48, ancho_util * 0.52]
    )
    tabla_encabezado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.8, colors.HexColor('#cbd5e1')),
        ('BOX', (1, 0), (1, 0), 1.0, colors.HexColor('#1e293b')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f8fafc')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 8))

    # ==========================================================================
    # 2. BLOQUE DE INFORMACIÓN DEL COMPRADOR
    # ==========================================================================
    comprador_nombre = factura.get('cliente') or 'CONSUMIDOR FINAL'
    comprador_ruc = factura.get('ruc') or '9999999999999'
    comprador_dir = factura.get('direccion') or 'Machala - Ecuador'
    comprador_tel = factura.get('telefono') or 'S/N'

    datos_comprador = [
        [
            Paragraph(f"<b>Razón Social / Nombres y Apellidos:</b> {comprador_nombre}", style_normal),
            Paragraph(f"<b>Identificación (RUC / Cédula):</b> {comprador_ruc}", style_normal)
        ],
        [
            Paragraph(f"<b>Fecha de Emisión:</b> {fecha_emision_str}", style_normal),
            Paragraph(f"<b>Teléfono:</b> {comprador_tel}", style_normal)
        ],
        [
            Paragraph(f"<b>Dirección Comprador:</b> {comprador_dir}", style_normal),
            Paragraph("<b>Guía de Remisión:</b> N/A", style_normal)
        ]
    ]

    tabla_comprador = Table(
        datos_comprador,
        colWidths=[ancho_util * 0.60, ancho_util * 0.40]
    )
    tabla_comprador.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_comprador)
    elementos.append(Spacer(1, 8))

    # ==========================================================================
    # 3. TABLA DE DETALLE DE PRODUCTOS
    # ==========================================================================
    filas_productos = [[
        Paragraph("Cód. Principal", style_th),
        Paragraph("Cant.", style_th),
        Paragraph("Descripción", style_th),
        Paragraph("Precio Unitario", style_th),
        Paragraph("Descuento", style_th),
        Paragraph("Precio Total", style_th)
    ]]

    suma_subtotales_items = 0.0
    for idx, item in enumerate(detalles, start=1):
        cod_prod = item.get('id_producto') or idx
        codigo_str = f"PROD-{int(cod_prod):04d}" if str(cod_prod).isdigit() else str(cod_prod)
        cant = int(item.get('cantidad', 1))
        desc_prod = str(item.get('nombre', 'Producto Tecnológico'))
        precio_unit = float(item.get('precio', 0.0))
        descuento = float(item.get('descuento', 0.0))
        subtotal_linea = float(item.get('subtotal', round(cant * precio_unit - descuento, 2)))
        suma_subtotales_items += subtotal_linea

        filas_productos.append([
            Paragraph(codigo_str, style_td_center),
            Paragraph(str(cant), style_td_center),
            Paragraph(desc_prod, style_normal),
            Paragraph(f"${precio_unit:,.2f}", style_td_right),
            Paragraph(f"${descuento:,.2f}", style_td_right),
            Paragraph(f"${subtotal_linea:,.2f}", style_td_right)
        ])

    tabla_detalles = Table(
        filas_productos,
        colWidths=[
            ancho_util * 0.14,
            ancho_util * 0.08,
            ancho_util * 0.39,
            ancho_util * 0.13,
            ancho_util * 0.12,
            ancho_util * 0.14
        ],
        repeatRows=1
    )
    tabla_detalles.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_detalles)
    elementos.append(Spacer(1, 10))

    # ==========================================================================
    # 4. BLOQUE INFERIOR DIVIDIDO (INFO ADICIONAL & PAGOS | LIQUIDACIÓN IVA 15%)
    # ==========================================================================
    monto_cabecera = float(factura.get('monto') or suma_subtotales_items or 0.0)
    # Desglose de impuestos (Tarifa vigente IVA 15% Ecuador)
    # Calculamos base imponible 15% e IVA 15% cuadrando exactamente con el VALOR TOTAL facturado
    valor_total = round(monto_cabecera, 2)
    subtotal_15 = round(valor_total / 1.15, 2)
    iva_15 = round(valor_total - subtotal_15, 2)
    subtotal_0 = 0.00
    subtotal_no_objeto = 0.00
    subtotal_exento = 0.00
    subtotal_sin_impuestos = subtotal_15
    total_descuento = 0.00

    forma_pago_sri = mapear_forma_pago_sri(factura.get('metodo_pago'))
    email_cliente = factura.get('email') or 'No registrado'

    # Sub-bloque Izquierdo: Información Adicional + Forma de Pago SRI
    tabla_info_adicional = Table(
        [
            [Paragraph("<b>INFORMACIÓN ADICIONAL</b>", style_bold)],
            [Paragraph(f"<b>Correo Electrónico:</b> {email_cliente}", style_small)],
            [Paragraph(f"<b>Teléfono:</b> {comprador_tel}", style_small)],
            [Paragraph(f"<b>Dirección:</b> {comprador_dir}", style_small)],
            [Paragraph(f"<b>Observaciones:</b> Comprobante electrónico emitido por {EMISOR_SRI['nombre_comercial']} (Estado: PAGADA).", style_small)]
        ],
        colWidths=[ancho_util * 0.54]
    )
    tabla_info_adicional.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    tabla_forma_pago = Table(
        [
            [
                Paragraph("<b>Forma de Pago (Catálogo SRI)</b>", style_small),
                Paragraph("<b>Valor</b>", style_td_right),
                Paragraph("<b>Plazo</b>", style_td_center)
            ],
            [
                Paragraph(forma_pago_sri, style_small),
                Paragraph(f"${valor_total:,.2f}", style_td_right),
                Paragraph("0 días", style_td_center)
            ]
        ],
        colWidths=[ancho_util * 0.34, ancho_util * 0.11, ancho_util * 0.09]
    )
    tabla_forma_pago.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    bloque_izquierdo_inferior = [
        tabla_info_adicional,
        Spacer(1, 6),
        tabla_forma_pago
    ]

    # Sub-bloque Derecho: Liquidación de Impuestos SRI
    filas_totales = [
        [Paragraph("SUBTOTAL 15%", style_small), Paragraph(f"${subtotal_15:,.2f}", style_td_right)],
        [Paragraph("SUBTOTAL 0%", style_small), Paragraph(f"${subtotal_0:,.2f}", style_td_right)],
        [Paragraph("SUBTOTAL NO OBJETO DE IVA", style_small), Paragraph(f"${subtotal_no_objeto:,.2f}", style_td_right)],
        [Paragraph("SUBTOTAL EXENTO DE IVA", style_small), Paragraph(f"${subtotal_exento:,.2f}", style_td_right)],
        [Paragraph("SUBTOTAL SIN IMPUESTOS", style_small), Paragraph(f"${subtotal_sin_impuestos:,.2f}", style_td_right)],
        [Paragraph("TOTAL DESCUENTO", style_small), Paragraph(f"${total_descuento:,.2f}", style_td_right)],
        [Paragraph("IVA 15%", style_small), Paragraph(f"${iva_15:,.2f}", style_td_right)],
        [Paragraph("<b>VALOR TOTAL</b>", style_bold), Paragraph(f"<b>${valor_total:,.2f}</b>", style_td_right)]
    ]

    tabla_totales = Table(
        filas_totales,
        colWidths=[ancho_util * 0.28, ancho_util * 0.14]
    )
    tabla_totales.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    tabla_pie = Table(
        [[bloque_izquierdo_inferior, tabla_totales]],
        colWidths=[ancho_util * 0.58, ancho_util * 0.42]
    )
    tabla_pie.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elementos.append(tabla_pie)

    doc.build(elementos)
    buffer.seek(0)
    return buffer, numero_sri


def generar_pdf_ride_nota_credito_sri(nc, detalles):
    """
    Genera en memoria (io.BytesIO) el PDF RIDE oficial del SRI para una Nota de Crédito (Código 04).
    Retorna (buffer_pdf, numero_sri_formateado).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.2 * cm,
        title=f"RIDE_NC_{nc.get('numero_comprobante', '')}"
    )

    ancho_util = letter[0] - (2.4 * cm)
    styles = getSampleStyleSheet()

    style_normal = ParagraphStyle(
        'SRINCNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )
    style_bold = ParagraphStyle(
        'SRINCBold',
        parent=style_normal,
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11
    )
    style_title_emisor = ParagraphStyle(
        'SRINCTitleEmisor',
        parent=style_bold,
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#0f172a')
    )
    style_title_doc = ParagraphStyle(
        'SRINCTitleDoc',
        parent=style_bold,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#b91c1c')
    )
    style_clave = ParagraphStyle(
        'SRINCClave',
        parent=style_normal,
        fontName='Courier-Bold',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor('#0f172a')
    )
    style_small = ParagraphStyle(
        'SRINCSmall',
        parent=style_normal,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#334155')
    )
    style_th = ParagraphStyle(
        'SRINCTH',
        parent=style_bold,
        fontSize=7.8,
        leading=10,
        alignment=1,
        textColor=colors.white
    )
    style_td_right = ParagraphStyle(
        'SRINCTDRight',
        parent=style_normal,
        fontSize=8,
        leading=10,
        alignment=2
    )
    style_td_center = ParagraphStyle(
        'SRINCTDCenter',
        parent=style_normal,
        fontSize=8,
        leading=10,
        alignment=1
    )

    id_nc = nc.get('id', 1)
    numero_sri = formatear_numero_sri(nc.get('numero_comprobante') or nc.get('numero'), id_nc)
    fecha_emision = nc.get('fecha_emision') or nc.get('fecha') or datetime.now().strftime('%Y-%m-%d')
    if hasattr(fecha_emision, 'strftime'):
        fecha_str = fecha_emision.strftime('%d/%m/%Y')
        fecha_autorizacion_str = fecha_emision.strftime('%d/%m/%Y 11:30:00')
    else:
        fecha_str = str(fecha_emision)
        fecha_autorizacion_str = f"{fecha_str} 11:30:00"

    # Clave de acceso con código 04 (Nota de Crédito)
    clave_base = generar_clave_acceso_sri(fecha_emision, EMISOR_SRI['ruc'], numero_sri, id_nc)
    cadena_48_nc = clave_base[:8] + "04" + clave_base[10:48]
    clave_acceso = f"{cadena_48_nc}{calcular_digito_modulo11(cadena_48_nc)}"

    elementos = []
    logo_flowable = obtener_elemento_logo_ride(ancho_max_pt=145, alto_max_pt=55)

    col_emisor = []
    if logo_flowable is not None:
        col_emisor.append(logo_flowable)
        col_emisor.append(Spacer(1, 5))
    else:
        col_emisor.append(Paragraph(f"<b>{EMISOR_SRI['nombre_comercial']}</b>", style_title_emisor))
        col_emisor.append(Spacer(1, 4))

    col_emisor.extend([
        Paragraph(f"<b>{EMISOR_SRI['nombre_comercial']}</b>", style_title_emisor),
        Spacer(1, 3),
        Paragraph(f"<b>Razón Social:</b> {EMISOR_SRI['razon_social']}", style_normal),
        Paragraph(f"<b>RUC:</b> {EMISOR_SRI['ruc']}", style_normal),
        Paragraph(f"<b>Dirección Matriz:</b> {EMISOR_SRI['direccion_matriz']}", style_normal),
        Paragraph(f"<b>Dirección Sucursal:</b> {EMISOR_SRI['direccion_sucursal']}", style_normal),
        Spacer(1, 3),
        Paragraph(f"<b>OBLIGADO A LLEVAR CONTABILIDAD:</b> {EMISOR_SRI['obligado_contabilidad']}", style_normal),
        Paragraph(f"<b>{EMISOR_SRI['regimen']}</b>", style_bold)
    ])

    col_tributaria = [
        Paragraph(f"<b>R.U.C.:</b> {EMISOR_SRI['ruc']}", style_bold),
        Spacer(1, 3),
        Paragraph("<b>NOTA DE CRÉDITO</b>", style_title_doc),
        Spacer(1, 2),
        Paragraph(f"<b>No.</b> {numero_sri}", style_bold),
        Spacer(1, 4),
        Paragraph("<b>NÚMERO DE AUTORIZACIÓN:</b>", style_small),
        Paragraph(clave_acceso, style_clave),
        Spacer(1, 3),
        Paragraph(f"<b>FECHA Y HORA DE AUTORIZACIÓN:</b> {fecha_autorizacion_str}", style_small),
        Paragraph(f"<b>AMBIENTE:</b> {EMISOR_SRI['ambiente']}", style_small),
        Paragraph(f"<b>EMISIÓN:</b> {EMISOR_SRI['emision']}", style_small),
        Spacer(1, 3),
        Paragraph("<b>CLAVE DE ACCESO:</b>", style_small),
        Paragraph(clave_acceso, style_clave)
    ]

    tabla_encabezado = Table(
        [[col_emisor, col_tributaria]],
        colWidths=[ancho_util * 0.48, ancho_util * 0.52]
    )
    tabla_encabezado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.75, colors.HexColor('#cbd5e1')),
        ('BOX', (1, 0), (1, 0), 1.0, colors.HexColor('#0f172a')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f8fafc')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 8))

    cliente_nombre = nc.get('cliente') or 'CONSUMIDOR FINAL'
    cliente_ruc = str(nc.get('ruc') or '9999999999999').strip()
    factura_mod_num = formatear_numero_sri(nc.get('factura_numero'), nc.get('id_factura', 1))
    fecha_fac_mod = str(nc.get('factura_fecha') or fecha_str)
    motivo_mod = str(nc.get('motivo') or 'Devolución total o parcial de bienes')

    filas_comprador = [
        [
            Paragraph(f"<b>Razón Social / Nombres y Apellidos:</b> {cliente_nombre}", style_normal),
            Paragraph(f"<b>Identificación:</b> {cliente_ruc}", style_normal)
        ],
        [
            Paragraph(f"<b>Fecha de Emisión:</b> {fecha_str}", style_normal),
            Paragraph("<b>Comprobante que se modifica:</b> FACTURA", style_normal)
        ],
        [
            Paragraph(f"<b>No. Comprobante Modificado:</b> {factura_mod_num}", style_normal),
            Paragraph(f"<b>Fecha Emisión (Comprobante a modificar):</b> {fecha_fac_mod}", style_normal)
        ],
        [
            Paragraph(f"<b>Razón de Modificación:</b> {motivo_mod}", style_normal),
            Paragraph("", style_normal)
        ]
    ]

    tabla_comprador = Table(filas_comprador, colWidths=[ancho_util * 0.58, ancho_util * 0.42])
    tabla_comprador.setStyle(TableStyle([
        ('SPAN', (0, 3), (1, 3)),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_comprador)
    elementos.append(Spacer(1, 10))

    encabezados_items = [
        Paragraph("Cód. Principal", style_th),
        Paragraph("Cant.", style_th),
        Paragraph("Descripción", style_th),
        Paragraph("Precio Unitario", style_th),
        Paragraph("Descuento", style_th),
        Paragraph("Precio Total", style_th)
    ]
    filas_detalle = [encabezados_items]

    for idx, item in enumerate(detalles, start=1):
        cod_prod = f"PROD-{int(item.get('id_producto') or idx):04d}"
        cantidad = int(item.get('cantidad', 1))
        nombre_prod = str(item.get('nombre', 'Producto'))
        precio_u = round(float(item.get('precio_unitario', 0.0)), 2)
        subtotal_item = round(float(item.get('subtotal', cantidad * precio_u)), 2)

        filas_detalle.append([
            Paragraph(cod_prod, style_td_center),
            Paragraph(str(cantidad), style_td_center),
            Paragraph(nombre_prod, style_normal),
            Paragraph(f"${precio_u:,.2f}", style_td_right),
            Paragraph("$0.00", style_td_right),
            Paragraph(f"${subtotal_item:,.2f}", style_td_right)
        ])

    tabla_detalles = Table(
        filas_detalle,
        colWidths=[
            ancho_util * 0.14,
            ancho_util * 0.08,
            ancho_util * 0.42,
            ancho_util * 0.12,
            ancho_util * 0.11,
            ancho_util * 0.13
        ]
    )
    tabla_detalles.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla_detalles)
    elementos.append(Spacer(1, 10))

    subtotal_15 = round(float(nc.get('subtotal_15', 0.0)), 2)
    subtotal_0 = round(float(nc.get('subtotal_0', 0.0)), 2)
    iva_15 = round(float(nc.get('iva', 0.0)), 2)
    valor_total = round(float(nc.get('total', 0.0)), 2)

    tabla_info_adicional = Table(
        [
            [Paragraph("<b>INFORMACIÓN ADICIONAL</b>", style_bold)],
            [Paragraph(f"<b>Documento Modificado:</b> Factura {factura_mod_num}", style_small)],
            [Paragraph(f"<b>Motivo SRI:</b> {motivo_mod}", style_small)],
            [Paragraph(f"<b>Email Cliente:</b> {nc.get('email') or 'N/A'}", style_small)]
        ],
        colWidths=[ancho_util * 0.54]
    )
    tabla_info_adicional.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    filas_totales = [
        [Paragraph("SUBTOTAL 15%", style_small), Paragraph(f"${subtotal_15:,.2f}", style_td_right)],
        [Paragraph("SUBTOTAL 0%", style_small), Paragraph(f"${subtotal_0:,.2f}", style_td_right)],
        [Paragraph("SUBTOTAL SIN IMPUESTOS", style_small), Paragraph(f"${subtotal_15 + subtotal_0:,.2f}", style_td_right)],
        [Paragraph("IVA 15%", style_small), Paragraph(f"${iva_15:,.2f}", style_td_right)],
        [Paragraph("<b>VALOR TOTAL DEVUELTO</b>", style_bold), Paragraph(f"<b>${valor_total:,.2f}</b>", style_td_right)]
    ]
    tabla_totales = Table(filas_totales, colWidths=[ancho_util * 0.28, ancho_util * 0.14])
    tabla_totales.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    tabla_pie = Table(
        [[tabla_info_adicional, tabla_totales]],
        colWidths=[ancho_util * 0.58, ancho_util * 0.42]
    )
    tabla_pie.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elementos.append(tabla_pie)

    doc.build(elementos)
    buffer.seek(0)
    return buffer, numero_sri


