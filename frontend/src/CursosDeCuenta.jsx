import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

function CursosDeCuenta() {
  const { cuentaId, usuarioId } = useParams();
  const [cursos, setCursos] = useState([]);
  const [sincronizando, setSincronizando] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchCursos = async () => {
      const response = await fetch(`/api/cuentas/${cuentaId}/cursos`);
      if (response.ok) {
        const data = await response.json();
        setCursos(data);
      } else {
        setCursos([]);
      }
    };
    fetchCursos();
  }, [cuentaId]);

  const sincronizar = async () => {
    setSincronizando(true);
    await fetch(`/api/cuentas/${cuentaId}/sincronizar_cursos`, { method: "POST" });
    // Polling
    const checkEstado = async () => {
      const res = await fetch(`/api/cuentas/${cuentaId}/sincronizacion`);
      const data = await res.json();
      if (data.estado === "sincronizando") {
        setTimeout(checkEstado, 2000);
      } else {
        setSincronizando(false);
        // Refresca cursos
        const response = await fetch(`/api/cuentas/${cuentaId}/cursos`);
        if (response.ok) {
          const data = await response.json();
          setCursos(data);
        }
      }
    };
    checkEstado();
  };

  return (
    <div>
      <h2>Cursos sincronizados</h2>
      <button onClick={sincronizar} disabled={sincronizando} style={{ marginBottom: "10px" }}>
        {sincronizando ? "Sincronizando..." : "Sincronizar"}
      </button>
      <ul>
        {cursos.length === 0 && <li>No hay cursos sincronizados.</li>}
        {cursos.map((curso) => (
          <li key={curso.id || curso.nombre}>
            <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${curso.id}/tareas`} style={{ color: "blue", textDecoration: "underline" }}>
              {curso.nombre}
            </Link>
          </li>
        ))}
      </ul>
      <button onClick={() => navigate(-1)} style={{ marginTop: "10px" }}>
        Volver
      </button>
    </div>
  );
}

export default CursosDeCuenta;
