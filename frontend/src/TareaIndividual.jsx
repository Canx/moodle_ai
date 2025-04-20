import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

function TareaIndividual() {
  const { tareaId, cursoId, cuentaId, usuarioId } = useParams();
  const [tarea, setTarea] = useState(null);
  const [desc, setDesc] = useState(null);
  const [entregas, setEntregas] = useState([]);
  const [descOpen, setDescOpen] = useState(false);
  const [entregasOpen, setEntregasOpen] = useState(false);

  // Mostrar la descripción local al cargar la tarea si existe
  useEffect(() => {
    if (tarea && tarea.descripcion) {
      setDesc(tarea.descripcion);
    }
  }, [tarea]);

  useEffect(() => {
    if (tareaId) {
      fetch(`/api/tareas/${tareaId}/entregas_pendientes`).then(res => res.json()).then(setEntregas);
    }
  }, [tareaId]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchTarea = async () => {
      let url = `/api/tareas/${tareaId}`;
      if (cursoId) url += `?curso_id=${cursoId}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setTarea(data);
      } else {
        setError("No se encontró la tarea. Puede que nunca se haya sincronizado o el curso no sea correcto.");
      }
    };
    fetchTarea();
  }, [tareaId]);

  const sincronizarTarea = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tareas/${tareaId}/sincronizar`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setDesc(data.descripcion);
        // Tras sincronizar, recarga entregas pendientes
        const entregasRes = await fetch(`/api/tareas/${tareaId}/entregas_pendientes`);
        if (entregasRes.ok) {
          const entregasData = await entregasRes.json();
          setEntregas(entregasData);
        }
      } else {
        setError("No se pudo sincronizar la tarea");
      }
    } catch (e) {
      setError("Error de red");
    }
    setLoading(false);
  };


  if (error) return <div style={{color:'red'}}>{error}</div>;
  if (!tarea) return <div>Cargando tarea...</div>;

  return (
    <div style={{position: 'relative', width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', display: 'flex', flexDirection: 'column'}}>
      {/* Breadcrumb visual */}
      {/* Resumen de la tarea */}
      <div style={{
        background: '#f7fafd', borderRadius: 12, padding: '18px 20px', marginBottom: 28, boxShadow: '0 2px 8px #1976d233',
        border: '2px solid #1976d2',
        display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 430, alignSelf: 'flex-start'
      }}>
        <div style={{fontWeight:700, fontSize:'1.13rem', color:'#1976d2', marginBottom:7, letterSpacing:0.5}}>Datos de la tarea</div>
        <div><b>ID Moodle:</b> {tarea.tarea_id}</div>
        <div><b>Calificación máxima:</b> {tarea.calificacion_maxima !== undefined && tarea.calificacion_maxima !== null ? tarea.calificacion_maxima : <span style={{color:'#aaa'}}>No disponible</span>}</div>
        <div><b>Estado:</b> {tarea.estado || <span style={{color:'#aaa'}}>No disponible</span>}</div>
        <div><b>Última sincronización:</b> {tarea.fecha_sincronizacion ? new Date(tarea.fecha_sincronizacion).toLocaleString() : <span style={{color:'#aaa'}}>No disponible</span>}</div>
      </div>
      <nav style={{fontSize: '1rem', marginBottom: 18, color: '#888', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4}} aria-label="breadcrumb">
        <Link to="/" style={{color: '#1976d2', textDecoration: 'none', fontWeight: 500}}>Inicio</Link>
        <span style={{margin: '0 6px'}}>›</span>
        <Link to={`/usuario/${usuarioId}/cuentas`} style={{color: '#1976d2', textDecoration: 'none', fontWeight: 500}}>Cuentas</Link>
        <span style={{margin: '0 6px'}}>›</span>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos`} style={{color: '#1976d2', textDecoration: 'none', fontWeight: 500}}>Cursos</Link>
        <span style={{margin: '0 6px'}}>›</span>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas`} style={{color: '#1976d2', textDecoration: 'none', fontWeight: 500}}>Tareas</Link>
        <span style={{margin: '0 6px'}}>›</span>
        <span style={{color: '#888', fontWeight: 500}}>Tarea</span>
      </nav>
      <div style={{display:'flex', gap:'16px', width:'100%', justifyContent:'flex-start', marginBottom:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas`} style={{color: '#1976d2', textDecoration: 'none', fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none'}}>&larr; Volver a tareas</Link>
        <button onClick={() => navigate(-1)} style={{ backgroundColor: '#4CAF50', color: '#fff', padding: '10px 20px', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight: 500 }}>
          Atrás
        </button>
      </div>
      <h2 style={{fontSize: '2rem', color: '#1976d2', marginBottom: 18, textAlign: 'center'}}>{tarea.titulo}</h2>
      <button onClick={sincronizarTarea} disabled={loading} style={{ background: '#1976d2', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 22px', fontWeight: 600, fontSize: '1rem', cursor: loading ? 'not-allowed' : 'pointer', marginBottom: '18px', boxShadow: loading ? 'none' : '0 2px 6px #1976d233', opacity: loading ? 0.6 : 1, transition: 'opacity 0.2s' }}>
        {loading ? "Sincronizando..." : "Sincronizar tarea"}
      </button>
      {error && <div style={{ color: "#d32f2f", background: '#fff0f0', borderRadius: 6, padding: '8px 14px', marginBottom: 10 }}>{error}</div>}
      {/* Descripción colapsable */}
      <div style={{marginBottom: 18}}>
        <button onClick={() => setDescOpen(o => !o)} style={{background: '#1976d2', color: '#fff', border: 'none', borderRadius: 7, padding: '7px 16px', fontWeight: 600, fontSize: '1rem', cursor: 'pointer', marginBottom: 6}}>
          {descOpen ? 'Ocultar descripción' : 'Mostrar descripción'}
        </button>
        {descOpen && desc && (
          <div style={{ marginTop: "10px", width: '100%', color: '#444', fontSize: '1.08rem', background: '#f7f7fa', borderRadius: 8, padding: 18 }} dangerouslySetInnerHTML={{ __html: desc }} />
        )}
      </div>
      {/* Entregas pendientes colapsable */}
      <div>
        <button onClick={() => setEntregasOpen(o => !o)} style={{background: '#1976d2', color: '#fff', border: 'none', borderRadius: 7, padding: '7px 16px', fontWeight: 600, fontSize: '1rem', cursor: 'pointer', marginBottom: 6}}>
          {entregasOpen ? 'Ocultar entregas pendientes' : `Ver entregas pendientes (${entregas.length})`}
        </button>
        {entregasOpen && (
          entregas.length === 0 ? <div style={{background:'#f7f7fa', borderRadius:8, padding:12, color:'#888'}}>No hay entregas pendientes de calificar.</div> :
          <div style={{overflowX:'auto'}}>
            <table style={{width:'100%', background:'#f7f7fa', borderRadius:8, marginTop:8, fontSize:'0.98rem'}}>
              <thead>
                <tr style={{background:'#e3eefd'}}>
                  <th style={{padding:'6px 10px'}}>Alumno</th>
                  <th style={{padding:'6px 10px'}}>Fecha entrega</th>
                  <th style={{padding:'6px 10px'}}>Archivo</th>
                  <th style={{padding:'6px 10px'}}>Estado</th>
                  <th style={{padding:'6px 10px'}}>Calificar</th>
                </tr>
              </thead>
              <tbody>
                {entregas.map((entrega, idx) => (
                  <tr key={idx}>
                    <td style={{padding:'6px 10px'}}>{entrega.nombre || 'Sin nombre'}</td>
                    <td style={{padding:'6px 10px'}}>{entrega.fecha_entrega}</td>
                    <td style={{padding:'6px 10px'}}>
                      {entrega.archivos && entrega.archivos.length > 0 ? (
                        <a href={entrega.archivos[0].url} target="_blank" rel="noopener noreferrer">{entrega.archivos[0].nombre}</a>
                      ) : 'Sin archivo'}
                    </td>
                    <td style={{padding:'6px 10px'}}>{entrega.estado}</td>
                    <td style={{padding:'6px 10px'}}>
                      {entrega.link_calificar && (
                        <a href={entrega.link_calificar} target="_blank" rel="noopener noreferrer" style={{marginRight:8, background:'#1976d2', color:'#fff', padding:'4px 10px', borderRadius:6, textDecoration:'none', fontWeight:500}}>Manual</a>
                      )}
                      <button onClick={async()=>{
                        await fetch(`/api/tareas/${tareaId}/evaluar`, {method:'POST'});
                        alert('Calificación automática iniciada.');
                      }} style={{background:'#27ae60', color:'#fff', padding:'4px 10px', border:'none', borderRadius:6, fontWeight:500, cursor:'pointer'}}>Auto</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {/* Overlay spinner */}
      {(loading || (tarea && tarea.estado === 'sincronizando')) && (
        <div style={{position:'absolute',top:0,left:0,right:0,bottom:0, background:'rgba(255,255,255,0.7)', borderRadius:18, display:'flex', alignItems:'center', justifyContent:'center'}}>
          <div className="lds-ring"><div></div><div></div><div></div><div></div></div>
        </div>
      )}
    </div>
  );
}

export default TareaIndividual;
