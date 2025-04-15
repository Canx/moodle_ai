// src/CursoTareas.jsx
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

function CursoTareas() {
  const { cursoId } = useParams();
  const [tareas, setTareas] = useState([]);

  useEffect(() => {
    const fetchTareas = async () => {
      const response = await fetch(`/api/cursos/${cursoId}/tareas`);
      const data = await response.json();
      setTareas(data);
    };

    fetchTareas();
  }, [cursoId]);

  return (
    <div className="p-4">
      <Link to="/" className="text-blue-500 underline">
        Volver a la lista de cursos
      </Link>
      <h2 className="text-lg font-bold mt-4">Tareas del Curso</h2>
      <ul>
        {tareas.map((tarea, index) => (
          <li key={index}>
            <a
              href={tarea.enlace}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-500 underline"
            >
              {tarea.nombre}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default CursoTareas;