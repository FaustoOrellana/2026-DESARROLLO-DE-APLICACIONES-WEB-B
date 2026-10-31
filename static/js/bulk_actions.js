/**
 * TechManager System v2.0.0
 * Componente Modular de Selección Múltiple y Acciones en Lote (Bulk Actions)
 * Soporta:
 *  - Catálogos Admin (/productos, /proveedores, /clientes) -> Eliminar seleccionados
 *  - Facturación Admin (/facturacion) -> Anular seleccionadas (Normativa SRI)
 *  - Catálogo Cliente (/productos) -> Agregar seleccionados al carrito
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const selectAllCheckbox = document.getElementById('selectAll');
        const rowCheckboxes = Array.from(document.querySelectorAll('.bulk-check'));
        const configEl = document.getElementById('bulkActionsConfig') || document.querySelector('[data-bulk-endpoint]');

        if (!configEl || rowCheckboxes.length === 0) {
            if (selectAllCheckbox) {
                selectAllCheckbox.disabled = true;
            }
            return;
        }

        const endpoint = configEl.dataset.bulkEndpoint || '';
        const mode = (configEl.dataset.bulkMode || 'delete').toLowerCase(); // 'delete' | 'anular' | 'cart'
        const moduleName = configEl.dataset.bulkModule || 'registros';

        // Inyectar estilos de la barra flotante inferior (Sticky Bottom Action Bar)
        injectBulkStyles();

        // Construir Barra Flotante Inferior y Modal de Confirmación Bootstrap 5
        const actionBar = createStickyActionBar(mode);
        const confirmModalEl = (mode === 'delete' || mode === 'anular')
            ? createConfirmModal(mode, moduleName)
            : null;
        const bsConfirmModal = confirmModalEl && window.bootstrap
            ? new bootstrap.Modal(confirmModalEl)
            : null;

        const countSpan = document.getElementById('bulkSelectedCount');
        const btnClear = document.getElementById('btnBulkClear');
        const btnPrimary = document.getElementById('btnBulkPrimaryAction');
        const btnConfirmExecute = document.getElementById('btnBulkConfirmExecute');

        function getSelectedCheckboxes() {
            return rowCheckboxes.filter(cb => !cb.disabled && cb.checked);
        }

        function getEnabledCheckboxes() {
            return rowCheckboxes.filter(cb => !cb.disabled);
        }

        function updateUIState() {
            const selected = getSelectedCheckboxes();
            const enabled = getEnabledCheckboxes();
            const count = selected.length;

            // Resaltar filas seleccionadas
            rowCheckboxes.forEach(cb => {
                const tr = cb.closest('tr');
                if (tr) {
                    tr.classList.toggle('table-active', cb.checked);
                }
            });

            // Sincronizar estado de #selectAll
            if (selectAllCheckbox) {
                if (enabled.length === 0) {
                    selectAllCheckbox.checked = false;
                    selectAllCheckbox.indeterminate = false;
                } else {
                    selectAllCheckbox.checked = count === enabled.length && count > 0;
                    selectAllCheckbox.indeterminate = count > 0 && count < enabled.length;
                }
            }

            // Actualizar contador y visibilidad de la barra flotante
            if (countSpan) {
                countSpan.textContent = count;
            }
            const modalCountSpan = document.getElementById('bulkModalCount');
            if (modalCountSpan) {
                modalCountSpan.textContent = count;
            }

            if (count >= 1) {
                actionBar.classList.add('bulk-bar-visible');
            } else {
                actionBar.classList.remove('bulk-bar-visible');
            }
        }

        // Evento en checkbox maestro (#selectAll)
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function () {
                const checked = selectAllCheckbox.checked;
                getEnabledCheckboxes().forEach(cb => {
                    cb.checked = checked;
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                });
                updateUIState();
            });
        }

        // Evento en cada checkbox individual (.bulk-check)
        rowCheckboxes.forEach(cb => {
            cb.addEventListener('change', function () {
                updateUIState();
            });
        });

        // Botón "Desmarcar todo"
        if (btnClear) {
            btnClear.addEventListener('click', function () {
                rowCheckboxes.forEach(cb => {
                    cb.checked = false;
                });
                if (selectAllCheckbox) {
                    selectAllCheckbox.checked = false;
                    selectAllCheckbox.indeterminate = false;
                }
                // Limpiar persistencia local si existe en catálogo cliente
                if (typeof window.limpiarMemoriaSeleccion === 'function') {
                    window.limpiarMemoriaSeleccion();
                }
                updateUIState();
            });
        }

        // Botón Principal de la Barra Flotante
        if (btnPrimary) {
            btnPrimary.addEventListener('click', function () {
                const selected = getSelectedCheckboxes();
                if (selected.length === 0) return;

                if (mode === 'cart') {
                    executeBulkRequest();
                } else if (bsConfirmModal) {
                    bsConfirmModal.show();
                } else {
                    if (window.confirm('¿Está seguro de ejecutar esta acción sobre los elementos seleccionados?')) {
                        executeBulkRequest();
                    }
                }
            });
        }

        // Botón de confirmación dentro del Modal de Bootstrap (Admin)
        if (btnConfirmExecute) {
            btnConfirmExecute.addEventListener('click', function () {
                executeBulkRequest();
            });
        }

        async function executeBulkRequest() {
            const selected = getSelectedCheckboxes();
            if (selected.length === 0 || !endpoint) return;

            const ids = selected.map(cb => cb.value);
            const payload = { ids: ids };

            // Para cliente en catálogo: adjuntar cantidades individuales por producto
            if (mode === 'cart') {
                const cantidades = {};
                ids.forEach(id => {
                    const inputCant = document.querySelector(`input[name="cantidad_${id}"]`);
                    const val = inputCant ? parseInt(inputCant.value, 10) : 1;
                    cantidades[id] = (!isNaN(val) && val > 0) ? val : 1;
                });
                payload.cantidades = cantidades;
            }

            // Para anulación de facturas (SRI): adjuntar motivo de auditoría
            if (mode === 'anular') {
                const inputMotivo = document.getElementById('bulkMotivoAnulacion');
                if (inputMotivo && inputMotivo.value.trim()) {
                    payload.motivo = inputMotivo.value.trim();
                }
            }

            const csrfToken = (
                window.CSRF_TOKEN ||
                (document.querySelector('meta[name="csrf-token"]') && document.querySelector('meta[name="csrf-token"]').getAttribute('content')) ||
                (document.querySelector('input[name="csrf_token"]') && document.querySelector('input[name="csrf_token"]').value) ||
                ''
            );

            const triggerBtn = (mode === 'cart') ? btnPrimary : (btnConfirmExecute || btnPrimary);
            const originalHtml = triggerBtn ? triggerBtn.innerHTML : '';
            if (triggerBtn) {
                triggerBtn.disabled = true;
                triggerBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Procesando...';
            }

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (bsConfirmModal) {
                    bsConfirmModal.hide();
                }

                if (response.ok && data.status === 'success') {
                    if (typeof window.limpiarMemoriaSeleccion === 'function') {
                        window.limpiarMemoriaSeleccion();
                    }
                    if (mode === 'cart' && data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else {
                        window.location.reload();
                    }
                } else {
                    // Si el backend registró un mensaje flash (ej. bloqueo estricto HTTP 400), recargar para mostrar la alerta Bootstrap
                    if (response.status === 400 && data && data.mensaje) {
                        window.location.reload();
                        return;
                    }
                    alert(data.mensaje || 'No se pudo completar la acción en lote.');
                    if (triggerBtn) {
                        triggerBtn.disabled = false;
                        triggerBtn.innerHTML = originalHtml;
                    }
                }
            } catch (err) {
                console.error('Error en acción masiva:', err);
                alert('Error de red al procesar la operación en lote.');
                if (triggerBtn) {
                    triggerBtn.disabled = false;
                    triggerBtn.innerHTML = originalHtml;
                }
            }
        }

        // Inicializar estado al cargar (compatible con checkboxes precargados)
        updateUIState();
    });

    function injectBulkStyles() {
        if (document.getElementById('bulkActionsStyles')) return;
        const style = document.createElement('style');
        style.id = 'bulkActionsStyles';
        style.textContent = `
            .bulk-sticky-bar {
                position: fixed;
                bottom: 1.25rem;
                left: 50%;
                transform: translate(-50%, 150%);
                opacity: 0;
                z-index: 1045;
                min-width: min(92vw, 680px);
                max-width: 95vw;
                background: rgba(15, 23, 42, 0.96);
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 1rem;
                padding: 0.85rem 1.35rem;
                box-shadow: 0 20px 35px -10px rgba(15, 23, 42, 0.45);
                backdrop-filter: blur(10px);
                transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.24s ease;
                pointer-events: none;
            }
            .bulk-sticky-bar.bulk-bar-visible {
                transform: translate(-50%, 0);
                opacity: 1;
                pointer-events: auto;
            }
            .bulk-count-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 2rem;
                height: 2rem;
                padding: 0 0.55rem;
                border-radius: 0.5rem;
                background: #3b82f6;
                color: #ffffff;
                font-weight: 700;
                font-size: 0.95rem;
            }
        `;
        document.head.appendChild(style);
    }

    function createStickyActionBar(mode) {
        let btnClass = 'btn-danger';
        let btnIcon = 'bi-trash';
        let btnText = 'Eliminar seleccionados';

        if (mode === 'anular') {
            btnClass = 'btn-warning text-dark';
            btnIcon = 'bi-x-octagon';
            btnText = 'Anular seleccionadas';
        } else if (mode === 'cart') {
            btnClass = 'btn-success';
            btnIcon = 'bi-cart-plus';
            btnText = 'Agregar seleccionados al carrito';
        }

        const bar = document.createElement('div');
        bar.id = 'bulkActionBar';
        bar.className = 'bulk-sticky-bar d-flex flex-wrap align-items-center justify-content-between gap-3';
        bar.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <span class="bulk-count-badge" id="bulkSelectedCount">0</span>
                <span class="fw-semibold">elementos seleccionados</span>
            </div>
            <div class="d-flex align-items-center gap-2">
                <button type="button" id="btnBulkClear" class="btn btn-outline-light btn-sm rounded-3 px-3">
                    <i class="bi bi-x-circle me-1"></i> Desmarcar todo
                </button>
                <button type="button" id="btnBulkPrimaryAction" class="btn ${btnClass} btn-sm fw-bold rounded-3 px-3 py-2 shadow-sm">
                    <i class="bi ${btnIcon} me-1"></i> ${btnText}
                </button>
            </div>
        `;
        document.body.appendChild(bar);
        return bar;
    }

    function createConfirmModal(mode, moduleName) {
        const isAnular = mode === 'anular';
        const isProductos = moduleName.toLowerCase().includes('producto');
        const headerClass = isAnular ? 'bg-warning text-dark' : 'bg-danger text-white';
        const btnCloseClass = isAnular ? '' : 'btn-close-white';
        const titleIcon = isAnular ? 'bi-x-octagon-fill' : 'bi-exclamation-triangle-fill';
        const titleText = isAnular
            ? 'Confirmar Anulación Masiva (Normativa SRI)'
            : `Confirmar Eliminación en Lote (${moduleName})`;
        const confirmBtnClass = isAnular ? 'btn-warning text-dark fw-bold' : 'btn-danger fw-bold';
        const confirmBtnIcon = isAnular ? 'bi-x-octagon' : 'bi-trash';
        const confirmBtnText = isAnular ? 'Sí, anular seleccionadas' : 'Sí, eliminar seleccionados';

        let detailHtml = '';
        if (isAnular) {
            detailHtml = `
                <p class="text-secondary mb-2">
                    Está a punto de cambiar a estado <strong>ANULADA</strong> un total de
                    <strong class="text-dark"><span id="bulkModalCount">0</span> comprobante(s)</strong>.
                </p>
                <div class="alert alert-warning border-0 rounded-3 small mb-3">
                    <i class="bi bi-shield-exclamation me-1"></i>
                    <strong>Regla Tributaria SRI:</strong> Los comprobantes electrónicos no se eliminan físicamente; se anularán reintegrando el stock al inventario y dejando constancia en la bitácora de auditoría.
                </div>
                <div class="mb-2">
                    <label for="bulkMotivoAnulacion" class="form-label fw-semibold small text-dark">Motivo de anulación para Auditoría:</label>
                    <input type="text" id="bulkMotivoAnulacion" class="form-control form-control-sm rounded-3"
                           value="Anulación en lote autorizada por Administración (SRI)"
                           placeholder="Especifique el motivo contable o tributario...">
                </div>
            `;
        } else if (isProductos) {
            detailHtml = `
                <p class="text-secondary mb-2">
                    ¿Está seguro de que desea eliminar físicamente
                    <strong class="text-dark"><span id="bulkModalCount">0</span> producto(s) seleccionado(s)</strong>?
                </p>
                <div class="alert alert-warning border-0 rounded-3 small mb-0">
                    <i class="bi bi-shield-lock-fill me-1"></i>
                    <strong>Bloqueo Contable Estricto:</strong> Los productos que registren comprobantes emitidos en <code>detalle_facturas</code> <strong>NO serán eliminados ni ocultados automáticamente</strong>. Si solo desea retirarlos de la venta, utilice la opción <strong>Archivar / Desactivar</strong>.
                </div>
            `;
        } else {
            detailHtml = `
                <p class="text-secondary mb-2">
                    ¿Está seguro de que desea procesar la baja/eliminación de
                    <strong class="text-dark"><span id="bulkModalCount">0</span> registro(s) seleccionado(s)</strong> en <strong>${moduleName}</strong>?
                </p>
                <div class="alert alert-light border rounded-3 small text-muted mb-0">
                    <i class="bi bi-info-circle text-primary me-1"></i>
                    Los registros con historial o movimientos asociados recibirán <strong>baja lógica (Soft Delete)</strong> para preservar la integridad referencial; aquellos sin dependencias se eliminarán de forma definitiva, quedando todo registrado en <strong>Auditoría</strong>.
                </div>
            `;
        }

        const modal = document.createElement('div');
        modal.id = 'bulkConfirmModal';
        modal.className = 'modal fade';
        modal.tabIndex = -1;
        modal.setAttribute('aria-hidden', 'true');
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content border-0 shadow-lg rounded-4 overflow-hidden">
                    <div class="modal-header ${headerClass}">
                        <h5 class="modal-title fw-bold">
                            <i class="bi ${titleIcon} me-2"></i> ${titleText}
                        </h5>
                        <button type="button" class="btn-close ${btnCloseClass}" data-bs-dismiss="modal" aria-label="Cerrar"></button>
                    </div>
                    <div class="modal-body py-4">
                        ${detailHtml}
                    </div>
                    <div class="modal-footer bg-light border-0">
                        <button type="button" class="btn btn-secondary rounded-3 px-3" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" id="btnBulkConfirmExecute" class="btn ${confirmBtnClass} rounded-3 px-4 shadow-sm">
                            <i class="bi ${confirmBtnIcon} me-1"></i> ${confirmBtnText}
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        return modal;
    }
})();
