// Código para controlar el juego
let casillas = document.querySelectorAll(".casilla");
let turno = "X";

casillas.forEach((casilla) => {
  casilla.addEventListener("click", () => {
    if (casilla.textContent === "") {
      casilla.textContent = turno;
      turno = turno === "X" ? "O" : "X";
    }
  });
});
