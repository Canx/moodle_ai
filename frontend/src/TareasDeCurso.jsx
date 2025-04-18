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
    <div style={{width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', textAlign: 'center'}}>
      <div style={{display:'flex', gap:'16px', marginBottom:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos`} style={{ textDecoration: "none", color: "#1976d2", fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none' }}>
          Volver a cursos
        </Link>
        <button onClick={() => navigate(-1)} style={{ backgroundColor: "#4CAF50", color: "#fff", padding: "10px 20px", border: "none", borderRadius: "5px", cursor: "pointer", fontWeight: 500 }}>
          Atrás
        </button>
      </div>
      <h2>Tareas del Curso</h2>
      <button onClick={sincronizarTareas} disabled={sincronizando} style={{ marginBottom: "10px", backgroundColor: "#4CAF50", color: "#fff", padding: "10px 20px", border: "none", borderRadius: "5px", cursor: "pointer" }}>
        {sincronizando ? "Sincronizando..." : "Sincronizar tareas"}
      </button>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: '20px', marginTop: '20px'}}>
        {tareas.length === 0 && <div style={{background: '#fff', borderRadius: '12px', boxShadow: '0 2px 8px #0001', padding: '18px 24px', minWidth: 260, maxWidth: 340, flex: '1 0 260px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}>No hay tareas sincronizadas.</div>}
        {tareas.map((tarea) => (
          <div key={tarea.id || tarea.nombre} style={{background: '#fff', borderRadius: '12px', boxShadow: '0 2px 8px #0001', padding: '18px 24px', minWidth: 260, maxWidth: 340, flex: '1 0 260px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}>
            <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas/${tarea.id}/detalle`} style={{ color: '#1976d2', fontWeight: 'bold', fontSize: '1.1rem', textDecoration: 'none', marginBottom: 8 }}>
              {tarea.titulo}
            </Link>
          </div>
        ))}
      </div>
      <div style={{display:'flex', gap:'16px', marginTop:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos`} style={{ textDecoration: "none", color: "#1976d2", fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none' }}>
          Volver a cursos
        </Link>
        <button onClick={() => navigate(-1)} style={{ backgroundColor: "#4CAF50", color: "#fff", padding: "10px 20px", border: "none", borderRadius: "5px", cursor: "pointer", fontWeight: 500 }}>
          Atrás
        </button>
      </div>
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
