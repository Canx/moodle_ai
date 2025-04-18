import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";

function TareasDeCurso() {
  const { cursoId, cuentaId, usuarioId } = useParams();
  const [tareas, setTareas] = useState([]);
  const [moodleUrl, setMoodleUrl] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const fetchTareas = async () => {
      const response = await fetch(`/api/cursos/${cursoId}/tareas`);
      if (response.ok) {
        const data = await response.json();
        setTareas(data);
      } else {
        setTareas([]);
      }
    };
    const fetchCuenta = async () => {
      const response = await fetch(`/api/cuentas/${cuentaId}`);
      if (response.ok) {
        const data = await response.json();
        setMoodleUrl(data.moodle_url);
      }
    };
    fetchTareas();
    fetchCuenta();
  }, [cursoId, cuentaId]);

  const [sincronizando, setSincronizando] = useState(false);

  const sincronizarTareas = async () => {
    setSincronizando(true);
    await fetch(`/api/cursos/${cursoId}/sincronizar_tareas`, { method: "POST" });
    // Polling para estado (opcional, aquí asumimos que es rápido)
    const response = await fetch(`/api/cursos/${cursoId}/tareas`);
    if (response.ok) {
      const data = await response.json();
      setTareas(data);
    }
    setSincronizando(false);
  };

  return (
    <div>
      <h2>Tareas del Curso</h2>
      <button onClick={sincronizarTareas} disabled={sincronizando} style={{ marginBottom: "10px" }}>
        {sincronizando ? "Sincronizando..." : "Sincronizar tareas"}
      </button>
      <ul>
        {tareas.length === 0 && <li>No hay tareas sincronizadas.</li>}
        {tareas.map((tarea, idx) => (
          <li key={tarea.id || tarea.titulo}>
            <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas/${tarea.id}/detalle`} style={{ color: "blue", textDecoration: "underline" }}>
              {tarea.titulo}
            </Link>
          </li>
        ))}
      </ul>
      <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos`} style={{ marginTop: "10px", display: "inline-block" }}>
        Volver a cursos
      </Link>
      <button onClick={() => navigate(-1)} style={{ marginLeft: "10px" }}>
        Atrás
      </button>
    </div>
  );
}

function TareaItem({ tarea, moodleUrl }) {
  const [desc, setDesc] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [open, setOpen] = React.useState(false);

  const handleToggle = async () => {
    setOpen((prev) => !prev);
  };

  const sincronizarDescripcion = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tareas/${tarea.id}/descripcion`);
      if (res.ok) {
        const data = await res.json();
        setDesc(data.descripcion);
      } else {
        setError("No se pudo obtener la descripción");
      }
    } catch (e) {
      setError("Error de red");
    }
    setLoading(false);
  };



  return (
    <li style={{marginBottom: 10}}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <span style={{ fontWeight: "bold" }}>{tarea.titulo}</span>
        {moodleUrl && (
          <a href={`${moodleUrl}/mod/assign/view.php?id=${tarea.tarea_id}`} target="_blank" rel="noopener noreferrer" style={{ marginLeft: "10px" }}>
            Ver en Moodle
          </a>
        )}
      </div>
      <button onClick={sincronizarDescripcion} disabled={loading} style={{ marginTop: "5px", marginBottom: "5px" }}>
        {loading ? "Sincronizando..." : "Sincronizar descripción"}
      </button>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {desc && <div style={{ marginLeft: "20px" }} dangerouslySetInnerHTML={{ __html: desc }} />}
    </li>
  );
}

export default TareasDeCurso;
