import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

function TareasDeCurso() {
  const { cursoId, cuentaId, usuarioId } = useParams();
  const [tareas, setTareas] = useState([]);

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
    fetchTareas();
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

  // state hooks para ocultación
  const [mostrarOcultas, setMostrarOcultas] = useState(false);
  const [tareasOcultas, setTareasOcultas] = useState([]);
  const [openMenuId, setOpenMenuId] = useState(null);

  return (
    <div style={{width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', textAlign: 'center'}}>
      <div style={{display:'flex', gap:'16px', marginBottom:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos`} style={{ textDecoration: "none", color: "#1976d2", fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none' }}>
          Volver a cursos
        </Link>
      </div>
      <h2>Tareas del Curso</h2>
      <button onClick={sincronizarTareas} disabled={sincronizando} style={{ marginBottom: "10px", backgroundColor: "#4CAF50", color: "#fff", padding: "10px 20px", border: "none", borderRadius: "5px", cursor: "pointer" }}>
        {sincronizando ? "Sincronizando..." : "Sincronizar tareas"}
      </button>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: '20px', marginTop: '20px'}}>
        {tareas.length === 0 && <div style={{background: '#fff', borderRadius: '12px', boxShadow: '0 2px 8px #0001', padding: '18px 24px', minWidth: 260, maxWidth: 340, flex: '1 0 260px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}>No hay tareas sincronizadas.</div>}
        {tareas.map((tarea) => (
          <div key={tarea.id || tarea.nombre} style={{position: 'relative', background: '#fff', borderRadius: '12px', boxShadow: '0 2px 8px #0001', padding: '18px 24px', minWidth: 260, maxWidth: 340, flex: '1 0 260px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}>
            <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas/${tarea.id}/detalle`} style={{ color: '#1976d2', fontWeight: 'bold', fontSize: '1.1rem', textDecoration: 'none', marginBottom: 8 }}>
              {tarea.titulo}
            </Link>
            <span style={{
              display: 'inline-block',
              marginTop: 6,
              padding: '4px 10px',
              borderRadius: 12,
              fontSize: '0.95em',
              fontWeight: 500,
              color: '#fff',
              background: tarea.estado === 'pendiente_calificar' ? '#f39c12' : tarea.estado === 'sin_entregas' ? '#888' : tarea.estado === 'sin_pendientes' ? '#27ae60' : '#bbb',
              alignSelf: 'flex-start'
            }}>
              {tarea.estado === 'pendiente_calificar' && 'Pendiente de calificar'}
              {tarea.estado === 'sin_entregas' && 'Sin entregas'}
              {tarea.estado === 'sin_pendientes' && 'Sin pendientes'}
              {!['pendiente_calificar','sin_entregas','sin_pendientes'].includes(tarea.estado) && (tarea.estado || 'Desconocido')}
            </span>
            {/* Menú de acciones */}
            <button onClick={() => setOpenMenuId(openMenuId === tarea.id ? null : tarea.id)} style={{position: 'absolute', top: 8, right: 8, background: 'transparent', border: 'none', fontSize: '1.2rem', cursor: 'pointer'}}>⋮</button>
            {openMenuId === tarea.id && (
              <div style={{position: 'absolute', top: 28, right: 8, background: '#fff', border: '1px solid #ccc', borderRadius: 4, boxShadow: '0 2px 6px rgba(0,0,0,0.1)', zIndex: 10}}>
                <div onClick={async () => {
                  await fetch(`/api/tareas/${tarea.id}/ocultar`, { method: 'POST' });
                  const res = await fetch(`/api/cursos/${cursoId}/tareas`);
                  if (res.ok) setTareas(await res.json());
                  setOpenMenuId(null);
                }} style={{padding: '6px 12px', cursor: 'pointer', whiteSpace: 'nowrap'}}>Ocultar</div>
              </div>
            )}
          </div>
        ))}
      </div>
      {/* Sección de tareas ocultas */}
      <div style={{ marginTop: 20, textAlign: 'center' }}>
        <button onClick={async () => {
          if (!mostrarOcultas) {
            const resOc = await fetch(`/api/cursos/${cursoId}/tareas/ocultas`);
            if (resOc.ok) setTareasOcultas(await resOc.json());
          }
          setMostrarOcultas(o => !o);
        }} style={{ marginBottom: 10, background: '#888', color: '#fff', padding: '10px 20px', border: 'none', borderRadius: 5, cursor: 'pointer' }}>
          {mostrarOcultas ? 'Ocultar tareas ocultas' : 'Ver tareas ocultas'}
        </button>
        {mostrarOcultas && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px' }}>
            {tareasOcultas.length === 0 && <div>No hay tareas ocultas.</div>}
            {tareasOcultas.map(tarea => (
              <div key={tarea.id} style={{ background: '#fff', borderRadius: 12, boxShadow: '0 2px 8px #0001', padding: '18px 24px', minWidth: 260, maxWidth: 340, flex: '1 0 260px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas/${tarea.id}/detalle`} style={{ color: '#1976d2', fontWeight: 'bold', fontSize: '1.1rem', textDecoration: 'none', marginBottom: 8 }}>
                  {tarea.titulo}
                </Link>
                <button onClick={async () => {
                  await fetch(`/api/tareas/${tarea.id}/mostrar`, { method: 'POST' });
                  const resOc2 = await fetch(`/api/cursos/${cursoId}/tareas/ocultas`);
                  if (resOc2.ok) setTareasOcultas(await resOc2.json());
                }} style={{ marginTop: 8, background: '#27ae60', color: '#fff', border: 'none', borderRadius: 5, padding: '6px 10px', cursor: 'pointer' }}>
                  Mostrar
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div style={{display:'flex', gap:'16px', marginTop:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos`} style={{ textDecoration: "none", color: "#1976d2", fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none' }}>
          Volver a cursos
        </Link>
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

  const sincronizarTarea = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tareas/${tarea.id}/sincronizar`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setDesc(data.descripcion);
      } else {
        setError("No se pudo sincronizar la tarea");
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
      <button onClick={sincronizarTarea} disabled={loading} style={{ marginTop: "5px", marginBottom: "5px" }}>
        {loading ? "Sincronizando..." : "Sincronizar tarea"}
      </button>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {desc && <div style={{ marginLeft: "20px" }} dangerouslySetInnerHTML={{ __html: desc }} />}
    </li>
  );
}

export default TareasDeCurso;
