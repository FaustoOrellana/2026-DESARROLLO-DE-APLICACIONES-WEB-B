document.addEventListener("DOMContentLoaded", () => {
    const listadoServiciosIniciales = [
        {
            titulo: "Inventario",
            descripcion: "Gestión avanzada de inventario tecnológico para hardware corporativo y software.",
            icono: "bi-boxes"
        },
        {
            titulo: "Monitoreo",
            descripcion: "Supervisión proactiva en tiempo real y monitoreo de estabilidad en redes empresariales.",
            icono: "bi-activity"
        },
        {
            titulo: "Administración",
            descripcion: "Control transparente y eficiente de licenciamiento y auditoría de software.",
            icono: "bi-shield-check"
        },
        {
            titulo: "Reportes",
            descripcion: "Generación automatizada de reportes detallados listos para la toma de decisiones estratégicas.",
            icono: "bi-graph-up-arrow"
        },
        {
            titulo: "Soporte",
            descripcion: "Soporte técnico integral y consultoría TI adaptada a las necesidades de tu organización.",
            icono: "bi-headset"
        }
    ];

    function inicializarModuloServicios() {
        const contenedorServicios = document.getElementById("contenedor-servicios-dinamicos");
        if (!contenedorServicios) return;
        contenedorServicios.innerHTML = ""; 

        listadoServiciosIniciales.forEach((servicio) => {
            const esTarjetaGrande = (servicio.titulo === "Reportes" || servicio.titulo === "Soporte");
            const claseColumna = esTarjetaGrande ? "col-md-6" : "col-md-4";

            const colDiv = document.createElement("div");
            colDiv.className = claseColumna;
            colDiv.innerHTML = `
                <div class="card h-100 custom-card p-4">
                    <div class="card-body p-0 d-flex flex-column gap-3">
                        <div class="service-icon-box">
                            <i class="bi ${servicio.icono}"></i>
                        </div>
                        <div>
                            <h5 class="card-title fw-bold text-dark mb-2">${servicio.titulo}</h5>
                            <p class="card-text text-muted small m-0" style="line-height: 1.6;">${servicio.descripcion}</p>
                        </div>
                    </div>
                </div>
            `;
            contenedorServicios.appendChild(colDiv);
        });
    }

    inicializarModuloServicios();
    const formRecurso = document.getElementById("form-recurso");
    const inputNombre = document.getElementById("recurso-nombre");
    const inputDescripcion = document.getElementById("recurso-descripcion");
    const selectCategoria = document.getElementById("recurso-categoria");
    
    const contenedorLista = document.getElementById("lista-recursos");
    const contadorTotal = document.getElementById("total-registros");
    const contenedorAlerta = document.getElementById("mensaje-alerta");

    let recursosTecnologicos = [
        {
            id: 1,
            nombre: "Servidor Dell PowerEdge",
            descripcion: "Servidor principal para respaldos y base de datos relacional.",
            categoria: "Hardware"
        },
        {
            id: 2,
            nombre: "Licencia Office 365 Enterprise",
            descripcion: "Suscripción anual para el equipo administrativo de soporte.",
            categoria: "Licencias"
        }
    ];

    function obtenerFeedbackElement(elemento) {
        return elemento.parentElement.querySelector(".invalid-feedback");
    }

    function renderizarRecursos() {
        if (!contenedorLista) return;
        contenedorLista.innerHTML = "";

        if (recursosTecnologicos.length === 0) {
            contenedorLista.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-info text-center py-4 shadow-sm m-0 border-0 rounded-4" role="alert">
                        <p class="mb-1 fw-bold">No hay recursos tecnológicos registrados en el inventario.</p>
                        <small class="text-muted">Utiliza el formulario de la izquierda para agregar un nuevo activo.</small>
                    </div>
                </div>
            `;
            if (contadorTotal) contadorTotal.innerText = "0";
            return;
        }

        recursosTecnologicos.forEach(recurso => {
            const colDiv = document.createElement("div");
            colDiv.classList.add("col-12", "col-sm-6", "tarjeta-animada");

            colDiv.innerHTML = `
                <div class="card h-100 shadow-sm border-start border-primary border-4 card-dinamica">
                    <div class="card-body d-flex flex-column justify-content-between p-3">
                        <div>
                            <span class="badge bg-light text-primary mb-2 border border-primary-subtle px-2 py-1">${recurso.categoria}</span>
                            <h5 class="card-title fw-bold text-dark small mb-1">${recurso.nombre}</h5>
                            <p class="card-text text-muted small m-0" style="line-height: 1.5;">${recurso.descripcion}</p>
                        </div>
                        <div class="text-end mt-3">
                            <button class="btn btn-link text-danger btn-sm p-0 text-decoration-none fw-medium btn-eliminar" data-id="${recurso.id}">
                                <i class="bi bi-trash3 me-1"></i> Eliminar
                            </button>
                        </div>
                    </div>
                </div>
            `;

            const botonEliminar = colDiv.querySelector(".btn-eliminar");
            botonEliminar.addEventListener("click", () => {
                eliminarRecurso(recurso.id);
            });

            contenedorLista.appendChild(colDiv);
        });

        if (contadorTotal) contadorTotal.innerText = recursosTecnologicos.length;
    }

    function eliminarRecurso(id) {
        recursosTecnologicos = recursosTecnologicos.filter(recurso => recurso.id !== id);
        renderizarRecursos();
    }

    // --- VALIDACIONES DE RECURSOS ---
    function validarNombre() {
        const valor = inputNombre.value.trim();
        const feedback = obtenerFeedbackElement(inputNombre);
        
        const cantidadLetras = (valor.match(/[a-zA-ZáéíóúÁÉÍÓÚñÑ]/g) || []).length;
        if (cantidadLetras < 2) {
            marcarInvalido(inputNombre);
            if (feedback) feedback.innerText = "El nombre del recurso debe contener al menos 2 letras.";
            return false;
        }

        if (valor.length > 50) {
            marcarInvalido(inputNombre);
            if (feedback) feedback.innerText = "El nombre no puede superar los 50 caracteres.";
            return false;
        }

        if (/(.{3,})\1/i.test(valor)) {
            marcarInvalido(inputNombre);
            if (feedback) feedback.innerText = "Evita secuencias de texto o números repetidos.";
            return false;
        }

        const palabras = valor.split(/\s+/);
        for (let palabra of palabras) {
            if (palabra.length > 15) {
                marcarInvalido(inputNombre);
                if (feedback) feedback.innerText = "Por favor, evita ingresar palabras excesivamente largas.";
                return false;
            }
            
            const tieneConsonantesExcesivas = /[bcdfghjklmnñpqrstvwxyz]{4,}/i.test(palabra);
            const noTieneVocales = palabra.length >= 3 && !/[aeiouáéíóúü]/i.test(palabra);

            if (tieneConsonantesExcesivas || noTieneVocales) {
                marcarInvalido(inputNombre);
                if (feedback) feedback.innerText = "Por favor, ingresa un nombre legible y coherente.";
                return false;
            }
        }

        const textoLimpio = valor.replace(/\s/g, "").toLowerCase();
        const cambiosAlfaNumericos = (textoLimpio.match(/[a-z][0-9]|[0-9][a-z]/g) || []).length;
        if (cambiosAlfaNumericos > 3) {
            marcarInvalido(inputNombre);
            if (feedback) feedback.innerText = "Por favor, ingresa un nombre de recurso válido y legible.";
            return false;
        }

        const caracteresRaros = (textoLimpio.match(/[ghjkwxz]/g) || []).length;
        if (caracteresRaros / textoLimpio.length > 0.60) {
            marcarInvalido(inputNombre);
            if (feedback) feedback.innerText = "El nombre contiene una combinación de letras inválida.";
            return false;
        }

        const regexNombreBase = /^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\-\.\_]+$/;
        if (!regexNombreBase.test(valor)) {
            marcarInvalido(inputNombre);
            if (feedback) feedback.innerText = "El nombre no debe contener caracteres especiales.";
            return false;
        }

        marcarValido(inputNombre);
        return true;
    }

    function validarDescripcion() {
        const valor = inputDescripcion.value.trim();
        const feedback = obtenerFeedbackElement(inputDescripcion);

        if (valor.length < 10) {
            marcarInvalido(inputDescripcion);
            if (feedback) feedback.innerText = "La descripción debe tener al menos 10 caracteres.";
            return false;
        }

        if (/(.{3,})\1/i.test(valor)) {
            marcarInvalido(inputDescripcion);
            if (feedback) feedback.innerText = "Evita repetir secuencias de letras sin sentido.";
            return false;
        }

        const letras = valor.replace(/\s/g, "").toLowerCase();
        const conteoLetras = {};
        for (let l of letras) {
            conteoLetras[l] = (conteoLetras[l] || 0) + 1;
            if (conteoLetras[l] / letras.length > 0.40) {
                marcarInvalido(inputDescripcion);
                if (feedback) feedback.innerText = "Por favor, ingresa un texto real y no letras al azar.";
                return false;
            }
        }

        const caracteresRaros = (letras.match(/[ghjkwxz]/g) || []).length;
        if (caracteresRaros / letras.length > 0.35) { 
            marcarInvalido(inputDescripcion);
            if (feedback) feedback.innerText = "El texto contiene combinaciones de letras inválidas.";
            return false;
        }
        
        const palabras = valor.split(/\s+/);
        if (palabras.length === 1) {
            marcarInvalido(inputDescripcion);
            if (feedback) feedback.innerText = "Por favor, estructura la descripción con al menos 2 palabras.";
            return false;
        }

        const tienePalabraContundente = palabras.some(p => p.length >= 5);
        if (!tienePalabraContundente) {
            marcarInvalido(inputDescripcion);
            if (feedback) feedback.innerText = "Por favor, ingresa una descripción más detailed y con palabras reales.";
            return false;
        }

        for (let palabra of palabras) {
            if (palabra.length > 15) {
                marcarInvalido(inputDescripcion);
                if (feedback) feedback.innerText = "Por favor, evita palabras excesivamente largas o falsas.";
                return false;
            }
            
            const tieneConsonantesExcesivas = /[bcdfghjklmnñpqrstvwxyz]{4,}/i.test(palabra);
            const noTieneVocales = palabra.length >= 3 && !/[aeiouáéíóúü]/i.test(palabra);

            if (tieneConsonantesExcesivas || noTieneVocales) {
                marcarInvalido(inputDescripcion);
                if (feedback) feedback.innerText = "Por favor, ingresa palabras legibles y coherentes.";
                return false;
            }
        }

        marcarValido(inputDescripcion);
        return true;
    }

    function validarCategoria() {
        if (selectCategoria.value !== "") {
            marcarValido(selectCategoria);
            return true;
        } else {
            marcarInvalido(selectCategoria);
            return false;
        }
    }

    function marcarValido(elemento) {
        elemento.classList.remove("is-invalid");
        elemento.classList.add("is-valid");
    }

    function marcarInvalido(elemento) {
        elemento.classList.remove("is-valid");
        elemento.classList.add("is-invalid");
    }

    function limpiarEstilosValidacion() {
        [inputNombre, inputDescripcion, selectCategoria].forEach(el => {
            el.classList.remove("is-valid", "is-invalid");
        });
    }

    inputNombre.addEventListener("input", validarNombre);
    inputNombre.addEventListener("blur", validarNombre);
    inputDescripcion.addEventListener("input", validarDescripcion);
    inputDescripcion.addEventListener("blur", validarDescripcion);
    selectCategoria.addEventListener("change", validarCategoria);
    selectCategoria.addEventListener("blur", validarCategoria);

    formRecurso.addEventListener("submit", (event) => {
        event.preventDefault(); 

        const esNombreValido = validarNombre();
        const esDescripcionValida = validarDescripcion();
        const esCategoriaValida = validarCategoria();

        if (!esNombreValido || !esDescripcionValida || !esCategoriaValida) {
            mostrarMensaje("Por favor, corrige los errores en el formulario antes de continuar.", "danger");
            return;
        }

        const nuevoRecurso = {
            id: Date.now(),
            nombre: inputNombre.value.trim(),
            descripcion: inputDescripcion.value.trim(),
            categoria: selectCategoria.value
        };

        recursosTecnologicos.push(nuevoRecurso);
        renderizarRecursos();

        mostrarMensaje("¡Recurso tecnológico registrado correctamente!", "success");
        formRecurso.reset();
        limpiarEstilosValidacion();
    });

    function mostrarMensaje(mensaje, tipo) {
        const alerta = document.createElement("div");
        alerta.className = `alert alert-${tipo} alert-dismissible fade show py-2 px-3 small border-0 rounded-3 shadow-sm mb-3`;
        alerta.setAttribute("role", "alert");
        alerta.innerHTML = `
            <i class="bi ${tipo === 'success' ? 'bi-check-circle-fill me-2' : 'bi-exclamation-triangle-fill me-2'}"></i>${mensaje}
            <button type="button" class="btn-close py-2" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        contenedorAlerta.innerHTML = "";
        contenedorAlerta.appendChild(alerta);

        if (tipo === "success") {
            setTimeout(() => { alerta.remove(); }, 3000);
        }
    }

    const formContacto = document.getElementById("form-contacto");
    const inputContactoNombre = document.getElementById("nombre");
    const inputContactoEmail = document.getElementById("email");
    const inputContactoAsunto = document.getElementById("asunto");
    const inputContactoMensaje = document.getElementById("mensaje");
    const contenedorAlertaContacto = document.getElementById("mensaje-alerta-contacto");

    function validarContactoNombre() {
            const valor = inputContactoNombre.value.trim();
            const feedback = obtenerFeedbackElement(inputContactoNombre);
            
            if (valor.length < 3) {
                marcarInvalido(inputContactoNombre);
                if (feedback) feedback.innerText = "El nombre completo debe tener al menos 3 caracteres.";
                return false;
            }

            if (valor.length > 60) {
                marcarInvalido(inputContactoNombre);
                if (feedback) feedback.innerText = "El nombre no puede superar los 60 caracteres.";
                return false;
            }

            if (/(.{3,})\1/i.test(valor)) {
                marcarInvalido(inputContactoNombre);
                if (feedback) feedback.innerText = "Evita secuencias de texto repetidas.";
                return false;
            }

            const palabras = valor.split(/\s+/);
            if (palabras.length < 2) {
                marcarInvalido(inputContactoNombre);
                if (feedback) feedback.innerText = "Por favor, ingresa tu nombre y apellido completos.";
                return false;
            }

            for (let palabra of palabras) {
                if (palabra.length > 15) {
                    marcarInvalido(inputContactoNombre);
                    if (feedback) feedback.innerText = "Evita ingresar palabras excesivamente largas.";
                    return false;
                }
                
                const tieneConsonantesExcesivas = /[bcdfghjklmnñpqrstvwxyz]{4,}/i.test(palabra);
                const noTieneVocales = palabra.length >= 3 && !/[aeiouáéíóúü]/i.test(palabra);

                if (tieneConsonantesExcesivas || noTieneVocales) {
                    marcarInvalido(inputContactoNombre);
                    if (feedback) feedback.innerText = "Por favor, ingresa un nombre legible y coherente.";
                    return false;
                }
            }

            const textoLimpio = valor.replace(/\s/g, "").toLowerCase();
            const caracteresRaros = (textoLimpio.match(/[ghjkwxz]/g) || []).length;
            if (textoLimpio.length > 0 && (caracteresRaros / textoLimpio.length > 0.45)) {
                marcarInvalido(inputContactoNombre);
                if (feedback) feedback.innerText = "El nombre contiene una combinación de letras inválida.";
                return false;
            }

            const regexNombreValido = /^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$/;
            if (!regexNombreValido.test(valor)) {
                marcarInvalido(inputContactoNombre);
                if (feedback) feedback.innerText = "El nombre solo debe contener letras y espacios.";
                return false;
            }

            marcarValido(inputContactoNombre);
            return true;
        }

    function validarContactoEmail() {
        const valor = inputContactoEmail.value.trim();
        const feedback = obtenerFeedbackElement(inputContactoEmail);
        const regexEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        
        if (regexEmail.test(valor)) {
            marcarValido(inputContactoEmail);
            return true;
        } else {
            marcarInvalido(inputContactoEmail);
            if (feedback) feedback.innerText = "Por favor, ingresa una estructura de correo válida (ejemplo@dominio.com).";
            return false;
        }
    }

    function validarContactoAsunto() {
        const valor = inputContactoAsunto.value.trim();
        const feedback = obtenerFeedbackElement(inputContactoAsunto);
        const cantidadLetras = (valor.match(/[a-zA-ZáéíóúÁÉÍÓÚñÑ]/g) || []).length;

        if (valor.length < 4 || cantidadLetras < 2) {
            marcarInvalido(inputContactoAsunto);
            if (feedback) feedback.innerText = "El asunto debe tener al menos 4 caracteres y contener letras.";
            return false;
        }

        if (/(.{3,})\1/i.test(valor)) {
            marcarInvalido(inputContactoAsunto);
            if (feedback) feedback.innerText = "Evita secuencias de texto repetidas sin sentido.";
            return false;
        }

        const letras = valor.replace(/\s/g, "").toLowerCase();
        const conteoLetras = {};
        for (let l of letras) {
            conteoLetras[l] = (conteoLetras[l] || 0) + 1;
            if (conteoLetras[l] / letras.length > 0.55) {
                marcarInvalido(inputContactoAsunto);
                if (feedback) feedback.innerText = "Por favor, ingresa un asunto real y no letras al azar o repetidas.";
                return false;
            }
        }

        const palabras = valor.split(/\s+/);
        for (let palabra of palabras) {
            if (palabra.length > 15) {
                marcarInvalido(inputContactoAsunto);
                if (feedback) feedback.innerText = "Por favor, evita ingresar palabras excesivamente largas.";
                return false;
            }
            
            const tieneConsonantesExcesivas = /[bcdfghjklmnñpqrstvwxyz]{4,}/i.test(palabra);
            const noTieneVocales = palabra.length >= 3 && !/[aeiouáéíóúü]/i.test(palabra);

            if (tieneConsonantesExcesivas || noTieneVocales) {
                marcarInvalido(inputContactoAsunto);
                if (feedback) feedback.innerText = "Por favor, ingresa un asunto legible y coherente.";
                return false;
            }

            if (/^[asdfghjklñ]{5,}$/i.test(palabra) && /(.)\1\1/.test(palabra)) {
                marcarInvalido(inputContactoAsunto);
                if (feedback) feedback.innerText = "Por favor, evita textos basura o combinaciones inválidas.";
                return false;
            }
        }

        marcarValido(inputContactoAsunto);
        return true;
    }

    function validarContactoMensaje() {
        const valor = inputContactoMensaje.value.trim();
        const feedback = obtenerFeedbackElement(inputContactoMensaje);

        if (valor.length < 10) {
            marcarInvalido(inputContactoMensaje);
            if (feedback) feedback.innerText = "El mensaje debe ser más detallado (mínimo 10 caracteres).";
            return false;
        }

        if (/(.{3,})\1/i.test(valor)) {
            marcarInvalido(inputContactoMensaje);
            if (feedback) feedback.innerText = "Evita repetir secuencias de letras sin sentido.";
            return false;
        }

        const letras = valor.replace(/\s/g, "").toLowerCase();
        const conteoLetras = {};
        for (let l of letras) {
            conteoLetras[l] = (conteoLetras[l] || 0) + 1;
            if (conteoLetras[l] / letras.length > 0.40) {
                marcarInvalido(inputContactoMensaje);
                if (feedback) feedback.innerText = "Por favor, ingresa un mensaje real y no letras al azar.";
                return false;
            }
        }

        const palabras = valor.split(/\s+/);
        if (palabras.length === 1) {
            marcarInvalido(inputContactoMensaje);
            if (feedback) feedback.innerText = "Por favor, estructura el mensaje con al menos 2 palabras.";
            return false;
        }

        marcarValido(inputContactoMensaje);
        return true;
    }
    function limpiarEstilosValidacionContacto() {
        [inputContactoNombre, inputContactoEmail, inputContactoAsunto, inputContactoMensaje].forEach(el => {
            if (el) el.classList.remove("is-valid", "is-invalid");
        });
    }

    function mostrarMensajeContacto(mensaje, tipo) {
        if (!contenedorAlertaContacto) return;
        const alerta = document.createElement("div");
        alerta.className = `alert alert-${tipo} alert-dismissible fade show py-2 px-3 small border-0 rounded-3 shadow-sm mb-3`;
        alerta.setAttribute("role", "alert");
        alerta.innerHTML = `
            <i class="bi ${tipo === 'success' ? 'bi-check-circle-fill me-2' : 'bi-exclamation-triangle-fill me-2'}"></i>${mensaje}
            <button type="button" class="btn-close py-2" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        contenedorAlertaContacto.innerHTML = "";
        contenedorAlertaContacto.appendChild(alerta);

        if (tipo === "success") {
            setTimeout(() => { alerta.remove(); }, 4000);
        }
    }

    if (formContacto) {
        inputContactoNombre.addEventListener("input", validarContactoNombre);
        inputContactoNombre.addEventListener("blur", validarContactoNombre);
        inputContactoEmail.addEventListener("input", validarContactoEmail);
        inputContactoEmail.addEventListener("blur", validarContactoEmail);
        inputContactoAsunto.addEventListener("input", validarContactoAsunto);
        inputContactoAsunto.addEventListener("blur", validarContactoAsunto);
        inputContactoMensaje.addEventListener("input", validarContactoMensaje);
        inputContactoMensaje.addEventListener("blur", validarContactoMensaje);

        formContacto.addEventListener("submit", (event) => {
            event.preventDefault(); 

            const esNombreValido = validarContactoNombre();
            const esEmailValido = validarContactoEmail();
            const esAsuntoValido = validarContactoAsunto();
            const esMensajeValido = validarContactoMensaje();

            if (!esNombreValido || !esEmailValido || !esAsuntoValido || !esMensajeValido) {
                mostrarMensajeContacto("Por favor, rellena todos los campos correctamente antes de enviar.", "danger");
                return;
            }

            const nombreCompleto = inputContactoNombre.value.trim();
            mostrarMensajeContacto(`¡Gracias por escribirnos, <strong>${nombreCompleto}</strong>! Tu mensaje ha sido enviado con éxito.`, "success");
            
            formContacto.reset();
            limpiarEstilosValidacionContacto();
        });
    }

    renderizarRecursos();
});