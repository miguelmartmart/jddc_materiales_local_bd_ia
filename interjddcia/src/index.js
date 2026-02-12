// interjddcia/src/index.js
// Importamos dependencias básicas para nuestro proyecto
import express from 'express';
import helmet from 'helmet';
import cors from 'cors';

// Creamos la aplicación Express
const app = express();

// Habilitamos Helmet y CORS para mejorar la seguridad
app.use(helmet());
app.use(cors());

// Puerto de escucha
const port = 3000;

// Inicializamos el servidor
app.listen(port, () => {
  console.log(`Servidor escuchando en el puerto ${port}`);
});
