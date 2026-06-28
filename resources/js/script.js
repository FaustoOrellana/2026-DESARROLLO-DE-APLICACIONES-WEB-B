document.addEventListener("DOMContentLoaded", () => {
    
    const formRecurso = document.getElementById("form-recurso");
    const inputNombre = document.getElementById("recurso-nombre");
    const inputDescripcion = document.getElementById("recurso-descripcion");
    const selectCategoria = document.getElementById("recurso-categoria");
    
    const contenedorLista = document.getElementById("lista-recursos");
    const contadorTotal = document.getElementById("total-registros");
    const contenedorAlerta = document.getElementById("mensaje-alerta");

    let totalCreados = 0;

    formRecurso.addEventListener("submit", (event) => {
        event.preventDefault();

        const nombre = inputNombre.value.trim();
        const descripcion = inputDescripcion.value.trim();
        const categoria = selectCategoria.value;

        if (nombre === "" || descripcion === "" || categoria === "") {
            mostrarMensaje("Por favor, complete todos los campos del formulario.", "danger");
            return;
        }

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