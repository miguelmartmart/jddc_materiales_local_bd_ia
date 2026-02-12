let turno = 'X';
let celdas = document.querySelectorAll('.casedilla');
let ganador = false;

celdas.forEach(celda => {
    celda.addEventListener('click', () => {
        if (celda.innerHTML === '' && !ganador) {
            celda.innerHTML = turno;
            verificarGanador();
            turno = (turno === 'X') ? 'O' : 'X';
        }
    });
});

function verificarGanador() {
    let combinatorias = [
        [celdas[0].innerHTML, celdas[1].innerHTML, celdas[2].innerHTML],
        [celdas[3].innerHTML, celdas[4].innerHTML, celdas[5].innerHTML],
        [celdas[6].innerHTML, celdas[7].innerHTML, celdas[8].innerHTML],
        [celdas[0].innerHTML, celdas[3].innerHTML, celdas[6].innerHTML],
        [celdas[1].innerHTML, celdas[4].innerHTML, celdas[7].innerHTML],
        [celdas[2].innerHTML, celdas[5].innerHTML, celdas[8].innerHTML],
        [celdas[0].innerHTML, celdas[4].innerHTML, celdas[8].innerHTML],
        [celdas[2].innerHTML, celdas[4].innerHTML, celdas[6].innerHTML]
    ];

    combinatorias.forEach(combinatoria => {
        if (combinatoria[0] !== '' && combinatoria[0] === combinatoria[1] && combinatoria[1] === combinatoria[2]) {
            ganador = true;
            let mensaje = document.createElement('div');
            mensaje.id = 'ganan';
            mensaje.innerHTML = 'Jugador ' + combinatoria[0] + ' gana!';
            document.body.appendChild(mensaje);
            reiniciarJuego();
        }
    });
}

function reiniciarJuego() {
    celdas.forEach(celda => {
        celda.innerHTML = '';
    });
    turno = 'X';
    ganador = false;
    let mensaje = document.getElementById('ganan');
    if (mensaje) {
        mensaje.remove();
    }
}
