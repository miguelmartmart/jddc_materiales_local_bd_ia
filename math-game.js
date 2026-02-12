// math-game.js
document.addEventListener("DOMContentLoaded", function() {
  // Seleccionamos el elemento donde se mostrará el juego
  var gameContainer = document.querySelector("#game-container");

  // Creamos un objeto para almacenar los datos del juego
  var gameData = {
    score: 0,
    questions: []
  };

  // Función para generar preguntas de sumas y restas
  function generateQuestion() {
    var num1 = Math.floor(Math.random() * 10);
    var num2 = Math.floor(Math.random() * 10);
    var operator = Math.random() < 0.5 ? "+" : "-";

    return {
      num1: num1,
      num2: num2,
      operator: operator
    };
  }

  // Función para mostrar la pregunta en pantalla
  function showQuestion() {
    var question = generateQuestion();
    var preguntaHTML = `
      <p>¿Cuánto es ${question.num1} ${question.operator} ${question.num2}?</p>
      <input type="number" id="answer" />
      <button id="submit">Enviar</button>
    `;

    gameContainer.innerHTML = preguntaHTML;
  }

  // Función para verificar la respuesta
  function checkAnswer() {
    var question = generateQuestion();
    var userAnswer = document.querySelector("#answer").value;
    var correctAnswer = eval(`${question.num1} ${question.operator} ${question.num2}`);

    if (userAnswer == correctAnswer) {
      gameData.score++;
      alert("¡Correcto!");
    } else {
      alert(`Lo siento, la respuesta correcta es ${correctAnswer}`);
    }

    showQuestion();
  }

  // Evento para enviar la respuesta
  document.querySelector("#submit").addEventListener("click", checkAnswer);

  // Mostramos la primera pregunta
  showQuestion();
});