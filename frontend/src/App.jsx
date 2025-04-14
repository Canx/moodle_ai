// src/App.jsx
import { useState } from 'react';
import axios from 'axios';

function App() {
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [url, setUrl] = useState("");
  const [profesorId, setProfesorId] = useState(null);
  const [cursos, setCursos] = useState([]);

  const registrarProfesor = async () => {
    try {
      const response = await axios.post("http://localhost:8000/registrar_profesor", {
        usuario,
        contrasena,
        moodle_url: url
      });
      alert("Profesor registrado correctamente");

      const resCursos = await axios.get("http://localhost:8000/cursos/1"); // provisionalmente usamos ID 1
      setProfesorId(1);
      setCursos(resCursos.data);
    } catch (error) {
      alert("Error al registrar profesor o conectar con Moodle");
      console.error(error);
    }
  };

  return (
    <div className="p-8 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Conectar con Moodle</h1>
      <input
        type="text"
        placeholder="Usuario de Moodle"
        className="border p-2 mb-2 w-full"
        value={usuario}
        onChange={(e) => setUsuario(e.target.value)}
      />
      <input
        type="password"
        placeholder="Contraseña de Moodle"
        className="border p-2 mb-2 w-full"
        value={contrasena}
        onChange={(e) => setContrasena(e.target.value)}
      />
      <input
        type="text"
        placeholder="URL de Moodle (sin /final)"
        className="border p-2 mb-2 w-full"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />
      <button
        type="button"
        onClick={registrarProfesor}
        className="bg-blue-600 text-white px-4 py-2 rounded"
      >
        Conectar y obtener cursos
      </button>

      {cursos.length > 0 && (
        <div className="mt-6">
          <h2 className="text-xl font-semibold mb-2">Cursos disponibles:</h2>
          <ul className="list-disc list-inside">
            {cursos.map((curso, index) => (
              <li key={index}>
                <a href={curso.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
                  {curso.nombre}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;