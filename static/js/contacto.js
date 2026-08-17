document.addEventListener("DOMContentLoaded", () => {
    const formContacto = document.getElementById("form-contacto");
    const inputContactoNombre = document.getElementById("nombre");
    const inputContactoEmail = document.getElementById("email");
    const inputContactoAsunto = document.getElementById("asunto");
    const inputContactoMensaje = document.getElementById("mensaje");
    const contenedorAlertaContacto = document.getElementById("mensaje-alerta-contacto");

    function obtenerFeedbackElement(elemento) {
        return elemento.parentElement.querySelector(".invalid-feedback");
    }

    function marcarValido(elemento) {
        elemento.classList.remove("is-invalid");
        elemento.classList.add("is-valid");
    }

    function marcarInvalido(elemento) {
        elemento.classList.remove("is-valid");
        elemento.classList.add("is-invalid");
    }

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
            if (feedback) feedback.innerText = "Por favor, ingresa un correo electrónico válido (ejemplo@dominio.com).";
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
});