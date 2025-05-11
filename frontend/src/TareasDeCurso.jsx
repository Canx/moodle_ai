import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { Spinner } from "react-bootstrap";

function TareasDeCurso() {
  const { cursoId, cuentaId, usuarioId } = useParams();
  const [tareas, setTareas] = useState([]);
  const [curso, setCurso] = useState(null);
  const [syncStatus, setSyncStatus] = useState({ estado: 'no_iniciado', fecha: null });
  const pendingCount = tareas.reduce((sum, t) => sum + (t.pendientes || 0), 0);

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

  useEffect(() => {
    const fetchCurso = async () => {
      const response = await fetch(`/api/cuentas/${cuentaId}/cursos`);
      if (response.ok) {
        const cursos = await response.json();
        const cursoActual = cursos.find(c => c.id === parseInt(cursoId));
        if (cursoActual) {
          setCurso(cursoActual);
        }
      }
    };
    fetchCurso();
  }, [cursoId, cuentaId]);

  useEffect(() => {
    let interval;
    const fetchStatus = async () => {
      try {
        // Obtener estado de sincronización
        const res = await fetch(`/api/cursos/${cursoId}/sincronizacion`);
        if (res.ok) {
          const data = await res.json();
          setSyncStatus(data);
          
          // Si está sincronizando o se completó, actualizar lista de tareas
          if (data.estado.startsWith('sincronizando') || data.estado === 'completada') {
            const resp = await fetch(`/api/cursos/${cursoId}/tareas`);
            if (resp.ok) {
              const tareasActualizadas = await resp.json();
              setTareas(tareasActualizadas);
            }
          }
          
          // Si se completó, detener el polling
          if (data.estado === 'completada') {
            clearInterval(interval);
          }
        }
      } catch {};
    };
    
    // Ejecutar inmediatamente y configurar el intervalo
    fetchStatus();
    interval = setInterval(fetchStatus, 3000); // Reducido a 3 segundos para mayor frecuencia de actualización
    
    // Limpiar el intervalo al desmontar
    return () => clearInterval(interval);
  }, [cursoId]);

  const [sincronizando, setSincronizando] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const sincronizarTareas = async () => {
    setSincronizando(true);
    setSyncStatus({ estado: 'sincronizando', fecha: new Date().toISOString() });
    try {
      await fetch(`/api/cursos/${cursoId}/sincronizar_tareas`, { method: "POST" });
    } catch (e) {
      console.error("Error iniciando sincronización:", e);
    }
    setSincronizando(false);
  };

  // state hooks para ocultación
  const [mostrarOcultas, setMostrarOcultas] = useState(false);
  const [tareasOcultas, setTareasOcultas] = useState([]);
  const [openMenuId, setOpenMenuId] = useState(null);

  return (
    <div style={{position: 'relative', width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', textAlign: 'center'}}>
      {/* Menú de acciones */}
      <div style={{position:'absolute', top:16, right:16}}>
        <button onClick={() => setMenuOpen(o => !o)} style={{background:'none', border:'none', cursor:'pointer', fontSize:'1.5rem'}}>⋮</button>
        {menuOpen && (
          <div style={{position:'absolute', right:0, marginTop:4, background:'#fff', border:'1px solid #ccc', borderRadius:4, boxShadow:'0 2px 6px rgba(0,0,0,0.1)'}}>
            <button onClick={() => { sincronizarTareas(); setMenuOpen(false); }} disabled={sincronizando} style={{display:'flex', alignItems:'center', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}>
              {sincronizando ? (<><Spinner animation="border" size="sm" className="me-2" />Sincronizando...</>) : 'Sincronizar tareas'}
            </button>
          </div>
        )}
      </div>
      <div style={{display:'flex', gap:'16px', marginBottom:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos`} style={{ textDecoration: "none", color: "#1976d2", fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none' }}>
          Volver a cursos
        </Link>
      </div>
      <h2 style={{color: '#1976d2', marginBottom: '8px'}}>
        {curso?.nombre}
      </h2>
      <h3 style={{color: '#666', marginBottom: '24px', fontWeight: 500}}>
        Tareas del curso
      </h3>
      {syncStatus.estado !== 'no_iniciado' && (
        <div style={{ marginBottom: '24px' }}>
          <div style={{ 
            marginBottom: '8px', 
            fontWeight: 500, 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            justifyContent: 'center',
            color: syncStatus.estado === 'completada' ? '#2e7d32' : '#1976d2'
          }}>
            {syncStatus.estado.startsWith('sincronizando') && <Spinner animation="border" size="sm" className="me-2" />}
            <span>
              {syncStatus.estado === 'completada' ? 'Última sincronización:' : syncStatus.estado}
            </span>
            {syncStatus.fecha && (
              <span style={{ color: '#666' }}>
                {new Date(syncStatus.fecha).toLocaleString('es-ES', {
                  day: '2-digit',
                  month: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </span>
            )}
          </div>
          {syncStatus.estado.startsWith('sincronizando') && syncStatus.porcentaje && (
            <div style={{ width: '100%', maxWidth: '600px', margin: '0 auto' }}>
              <div style={{
                width: '100%',
                height: '6px',
                backgroundColor: '#e0e0e0',
                borderRadius: '3px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${syncStatus.porcentaje}%`,
                  height: '100%',
                  backgroundColor: '#1976d2',
                  transition: 'width 0.3s ease-in-out'
                }} />
              </div>
              <div style={{ 
                textAlign: 'center',
                marginTop: '4px',
                fontSize: '0.9rem',
                color: '#666'
              }}>
                {Math.round(syncStatus.porcentaje)}%
              </div>
            </div>
          )}
        </div>
      )}
      {pendingCount > 0 && (
        <div style={{ 
          marginBottom: '12px', 
          fontWeight: 500,
          color: '#d32f2f'
        }}>
          Por calificar: {pendingCount}
        </div>
      )}
      <div style={{display: 'flex', flexWrap: 'wrap', gap: '20px', marginTop: '20px'}}>
        {tareas.length === 0 && <div style={{background: '#fff', borderRadius: '12px', boxShadow: '0 2px 8px #0001', padding: '18px 24px', minWidth: 260, maxWidth: 340, flex: '1 0 260px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}>No hay tareas sincronizadas.</div>}
        {tareas.map((tarea) => (
          <div key={tarea.id || tarea.nombre} style={{
            position: 'relative',
            background: tarea.pendientes > 0 ? '#fef6f6' : (tarea.entregadas > 0 ? '#f6fef6' : '#fff'),
            borderRadius: '12px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            borderLeft: tarea.pendientes > 0 ? '4px solid #ef5350' : (tarea.entregadas > 0 ? '4px solid #4caf50' : '4px solid #e0e0e0'),
            padding: '18px 24px',
            minWidth: 260,
            maxWidth: 340,
            flex: '1 0 260px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            transition: 'all 0.2s ease'
          }}>
            <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas/${tarea.id}/detalle`} 
                  style={{ color: '#1976d2', fontWeight: '600', fontSize: '1.1rem', textDecoration: 'none', marginBottom: 12 }}>
              {tarea.titulo}
            </Link>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'flex-start', 
                gap: '8px',
                fontSize: '0.95rem',
                color: '#666'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  background: '#edf4fc',
                  color: '#1976d2',
                  fontWeight: '500'
                }}>
                  Entregadas: {tarea.entregadas}
                </div>
                <div style={{ 
                  display: 'flex',
                  alignItems: 'center',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  background: tarea.pendientes > 0 ? '#ffeaea' : '#edf7ed',
                  color: tarea.pendientes > 0 ? '#d32f2f' : '#2e7d32',
                  fontWeight: '500'
                }}>
                  Por calificar: {tarea.pendientes}
                </div>
              </div>

              {tarea.estado === 'sin_entregas' && (
                <div style={{
                  display: 'inline-block',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '0.95em',
                  fontWeight: '500',
                  color: '#fff',
                  background: '#9e9e9e',
                  alignSelf: 'flex-start'
                }}>
                  Sin entregas
                </div>
              )}
            </div>

            {/* Menú de acciones */}
            <button onClick={() => setOpenMenuId(openMenuId === tarea.id ? null : tarea.id)} 
                    style={{
                      position: 'absolute', 
                      top: 8, 
                      right: 8, 
                      background: 'transparent', 
                      border: 'none', 
                      fontSize: '1.2rem', 
                      cursor: 'pointer',
                      color: '#666',
                      padding: '4px',
                      borderRadius: '4px',
                      transition: 'background-color 0.2s ease'
                    }}
                    onMouseOver={e => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                    onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}>
              ⋮
            </button>
            {openMenuId === tarea.id && (
              <div style={{
                position: 'absolute', 
                top: 28, 
                right: 8, 
                background: '#fff', 
                border: '1px solid #e0e0e0', 
                borderRadius: 8, 
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)', 
                zIndex: 10
              }}>
                <div onClick={async () => {
                  // Iniciar sincronización y cerrar menú
                  await fetch(`/api/tareas/${tarea.id}/sincronizar`, { method: 'POST' });
                  setOpenMenuId(null);
                  
                  // Marcar estado de tarea como sincronizando en UI
                  setTareas(ts => ts.map(x => x.id === tarea.id ? {...x, estado: 'sincronizando'} : x));
                  
                  // Polling 5s usando lista de tareas para refrescar counts y estado
                  const intervalId = setInterval(async () => {
                    const resList = await fetch(`/api/cursos/${cursoId}/tareas`);
                    if (!resList.ok) return;
                    const list = await resList.json();
                    const updated = list.find(u => u.id === tarea.id);
                    if (updated && updated.descripcion !== tarea.descripcion) {
                      clearInterval(intervalId);
                      setTareas(ts => ts.map(x => x.id === tarea.id ? updated : x));
                    }
                  }, 5000);
                }} 
                style={{
                  padding: '8px 16px',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'background-color 0.2s ease',
                  color: '#1976d2',
                  fontSize: '0.95rem'
                }}
                onMouseOver={e => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                onMouseOut={e => e.currentTarget.style.backgroundColor = '#fff'}>
                  Sincronizar tarea
                </div>
                <div onClick={async () => {
                  await fetch(`/api/tareas/${tarea.id}/ocultar`, { method: 'POST' });
                  const res = await fetch(`/api/cursos/${cursoId}/tareas`);
                  if (res.ok) setTareas(await res.json());
                  setOpenMenuId(null);
                }} 
                style={{
                  padding: '8px 16px',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'background-color 0.2s ease',
                  color: '#d32f2f',
                  fontSize: '0.95rem',
                  borderTop: '1px solid #e0e0e0'
                }}
                onMouseOver={e => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                onMouseOut={e => e.currentTarget.style.backgroundColor = '#fff'}>
                  Ocultar
                </div>
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
