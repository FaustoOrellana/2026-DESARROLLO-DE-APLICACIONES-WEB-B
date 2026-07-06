document.addEventListener("DOMContentLoaded", () => {
    
    const formRecurso = document.getElementById("form-recurso");
    const inputNombre = document.getElementById("recurso-nombre");
    const inputDescripcion = document.getElementById("recurso-descripcion");
    const selectCategoria = document.getElementById("recurso-categoria");
    
    const contenedorLista = document.getElementById("lista-recursos");
    const contadorTotal = document.getElementById("total-registros");
    const contenedorAlerta = document.getElementById("mensaje-alerta");

    let totalCreados = 0;

    function validarNombre() {
        const valor = inputNombre.value.trim();
        
        const cantidadLetras = (valor.match(/[a-zA-ZáéíóúÁÉÍÓÚñÑ]/g) || []).length;
        if (cantidadLetras < 2) {
            marcarInvalido(inputNombre);
            inputNombre.nextElementSibling.innerText = "El nombre del recurso debe contener al menos 2 letras.";
            return false;
        }

        if (valor.length > 50) {
            marcarInvalido(inputNombre);
            inputNombre.nextElementSibling.innerText = "El nombre no puede superar los 50 caracteres.";
            return false;
        }

        if (/(.{3,})\1/i.test(valor)) {
            marcarInvalido(inputNombre);
            inputNombre.nextElementSibling.innerText = "Evita secuencias de texto o números repetidos.";
            return false;
        }

        const palabras = valor.split(/\s+/);
        for (let palabra of palabras) {
            if (palabra.length > 15) {
                marcarInvalido(inputNombre);
                inputNombre.nextElementSibling.innerText = "Por favor, evita ingresar palabras excesivamente largas.";
                return false;
            }
            
            const tieneConsonantesExcesivas = /[bcdfghjklmnñpqrstvwxyz]{4,}/i.test(palabra);
            // Detecta palabras de 3 o más letras que no tengan ninguna vocal
            const noTieneVocales = palabra.length >= 3 && !/[aeiouáéíóúü]/i.test(palabra);

            if (tieneConsonantesExcesivas || noTieneVocales) {
                marcarInvalido(inputNombre);
                inputNombre.nextElementSibling.innerText = "Por favor, ingresa un nombre legible y coherente.";
                return false;
            }
        }

        const textoLimpio = valor.replace(/\s/g, "").toLowerCase();
        const cambiosAlfaNumericos = (textoLimpio.match(/[a-z][0-9]|[0-9][a-z]/g) || []).length;
        if (cambiosAlfaNumericos > 3) {
            marcarInvalido(inputNombre);
            inputNombre.nextElementSibling.innerText = "Por favor, ingresa un nombre de recurso válido y legible.";
            return false;
        }

        const caracteresRaros = (textoLimpio.match(/[ghjkwxz]/g) || []).length;
        if (caracteresRaros / textoLimpio.length > 0.60) {
            marcarInvalido(inputNombre);
            inputNombre.nextElementSibling.innerText = "El nombre contiene una combinación de letras inválida.";
            return false;
        }

        const regexNombreBase = /^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\-\.\_]+$/;
        if (!regexNombreBase.test(valor)) {
            marcarInvalido(inputNombre);
            inputNombre.nextElementSibling.innerText = "El nombre no debe contener caracteres especiales.";
            return false;
        }

        marcarValido(inputNombre);
        return true;
    }

    function validarDescripcion() {
        const valor = inputDescripcion.value.trim();

        if (valor.length < 10) {
            marcarInvalido(inputDescripcion);
            inputDescripcion.nextElementSibling.innerText = "La descripción debe tener al menos 10 caracteres.";
            return false;
        }

        if (/(.{3,})\1/i.test(valor)) {
            marcarInvalido(inputDescripcion);
            inputDescripcion.nextElementSibling.innerText = "Evita repetir secuencias de letras sin sentido.";
            return false;
        }

        const letras = valor.replace(/\s/g, "").toLowerCase();
        const conteoLetras = {};
        for (let l of letras) {
            conteoLetras[l] = (conteoLetras[l] || 0) + 1;
            if (conteoLetras[l] / letras.length > 0.40) {
                marcarInvalido(inputDescripcion);
                inputDescripcion.nextElementSibling.innerText = "Por favor, ingresa un texto real y no letras al azar.";
                return false;
            }
        }

        const caracteresRaros = (letras.match(/[ghjkwxz]/g) || []).length;
        if (caracteresRaros / letras.length > 0.35) { 
            marcarInvalido(inputDescripcion);
            inputDescripcion.nextElementSibling.innerText = "El texto contiene combinaciones de letras inválidas.";
            return false;
        }
        
        const palabras = valor.split(/\s+/);

        if (palabras.length === 1) {
            marcarInvalido(inputDescripcion);
            inputDescripcion.nextElementSibling.innerText = "Por favor, estructura la descripción con al menos 2 palabras.";
            return false;
        }

        const tienePalabraContundente = palabras.some(p => p.length >= 5);
        if (!tienePalabraContundente) {
            marcarInvalido(inputDescripcion);
            inputDescripcion.nextElementSibling.innerText = "Por favor, ingresa una descripción más detallada y con palabras reales.";
            return false;
        }

        for (let palabra of palabras) {
            if (palabra.length > 15) {
                marcarInvalido(inputDescripcion);
                inputDescripcion.nextElementSibling.innerText = "Por favor, evita palabras excesivamente largas o falsas.";
                return false;
            }
            
            const tieneConsonantesExcesivas = /[bcdfghjklmnñpqrstvwxyz]{4,}/i.test(palabra);
            const noTieneVocales = palabra.length >= 3 && !/[aeiouáéíóúü]/i.test(palabra);

            if (tieneConsonantesExcesivas || noTieneVocales) {
                marcarInvalido(inputDescripcion);
                inputDescripcion.nextElementSibling.innerText = "Por favor, ingresa palabras legibles y coherentes.";
                return false;
            }
        }

        marcarValido(inputDescripcion);
        return true;
    }

    function validarCategoria() {
        const valor = selectCategoria.value;
        if (valor !== "") {
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
        const elementos = [inputNombre, inputDescripcion, selectCategoria];
        elementos.forEach(el => {
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

        const nombre = inputNombre.value.trim();
        const descripcion = inputDescripcion.value.trim();
        const categoria = selectCategoria.value;

        mostrarMensaje("¡Recurso tecnológico registrado correctamente!", "success");

        const colDiv = document.createElement("div");
        colDiv.classList.add("col-12", "col-sm-6", "tarjeta-animada"); 

        colDiv.innerHTML = `
            <div class="card h-100 shadow-sm border-start border-primary border-4 card-dinamica">
                <div class="card-body d-flex flex-column justify-content-between">
                    <div>
                        <span class="badge bg-secondary mb-2">${categoria}</span>
                        <h5 class="card-title fw-bold text-dark">${nombre}</h5>
                        <p class="card-text text-muted small">${descripcion}</p>
                    </div>
                    <div class="text-end mt-3">
                        <button class="btn btn-outline-danger btn-sm btn-eliminar">
                            Eliminar
                        </button>
                    </div>
                </div>
            </div>
        `;

        const botonEliminar = colDiv.querySelector(".btn-eliminar");
        botonEliminar.addEventListener("click", () => {
            colDiv.remove();
            totalCreados--;
            contadorTotal.innerText = totalCreados;
        });

        contenedorLista.appendChild(colDiv);
        totalCreados++;
        contadorTotal.innerText = totalCreados;

        formRecurso.reset();
        limpiarEstilosValidacion();
    });

    function mostrarMensaje(mensaje, tipo) {
        const alerta = document.createElement("div");
        alerta.classList.add("alert", `alert-${tipo}`, "alert-dismissible", "fade", "show", "py-2", "small");
        alerta.setAttribute("role", "alert");
        alerta.innerHTML = `
            ${mensaje}
            <button type="button" class="btn-close py-2" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        contenedorAlerta.innerHTML = "";
        contenedorAlerta.appendChild(alerta);

        if (tipo === "success") {
            setTimeout(() => {
                alerta.remove();
            }, 3000);
        }
    }
});