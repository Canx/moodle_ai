// src/App.jsx
import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Route, Routes, Link } from "react-router-dom";
import CursoTareas from "./CursoTareas";
import RegistroUsuario from "./RegistroUsuario";
import CuentasMoodle from "./CuentasMoodle";

function App() {
  const [usuarioId, setUsuarioId] = useState(null); // Estado para el usuario autenticado
  const [cursos, setCursos] = useState([]);

  // Función para obtener cursos desde el backend
  const obtenerCursos = async () => {
    const response = await fetch("/api/cursos", {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    const data = await response.json();
    setCursos(data);
  };

  // Función para sincronizar cursos (scraping)
  const sincronizarCursos = async () => {
    const response = await fetch("/api/cursos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuarioId }),
    });
    const data = await response.json();
    setCursos(data);
  };

  return (
    <Router>
      <div className="p-4">
        <nav className="mb-4">
          <Link to="/" className="mr-4 text-blue-500 underline">
            Inicio
          </Link>
          <Link to="/registro" className="mr-4 text-blue-500 underline">
            Registro
          </Link>
          {usuarioId && (
            <Link to="/cuentas" className="text-blue-500 underline">
              Mis Cuentas de Moodle
            </Link>
          )}
        </nav>

        <Routes>
          {/* Página principal con la lista de cursos */}
          <Route
            path="/"
            element={
              <div>
                <h2 className="text-lg font-bold">Cursos</h2>
                <button
                  type="button"
                  onClick={obtenerCursos}
                  className="bg-gray-600 text-white px-4 py-2 rounded mb-2"
                >
                  Refrescar cursos
                </button>
                <ul>
                  {cursos.map((curso) => (
                    <li key={curso.id}>
                      <Link
                        to={`/cursos/${curso.id}`}
                        className="text-blue-500 underline"
                      >
                        {curso.nombre}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            }
          />

          {/* Página para registrar usuarios */}
          <Route
            path="/registro"
            element={<RegistroUsuario setUsuarioId={setUsuarioId} />}
          />

          {/* Página para gestionar cuentas de Moodle */}
          <Route
            path="/cuentas"
            element={<CuentasMoodle usuarioId={usuarioId} />}
          />

          {/* Página para mostrar las tareas de un curso */}
          <Route path="/cursos/:cursoId" element={<CursoTareas />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;