import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

function TareaIndividual() {
  const { tareaId, cursoId, cuentaId, usuarioId } = useParams();
  const [tarea, setTarea] = useState(null);
  const [desc, setDesc] = useState(null);
  const [entregas, setEntregas] = useState([]);
  const [descOpen, setDescOpen] = useState(false);
  const [entregasOpen, setEntregasOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

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
      {/* Menú de acciones */}
      <div style={{position: 'absolute', top: 16, right: 16}}>
        <button onClick={() => setMenuOpen(o => !o)} style={{background:'none', border:'none', cursor:'pointer', fontSize:'1.5rem'}}>⋮</button>
        {menuOpen && (
          <div style={{position:'absolute', right:0, marginTop:4, background:'#fff', border:'1px solid #ccc', borderRadius:4, boxShadow:'0 2px 6px rgba(0,0,0,0.2)'}}>
            <button onClick={() => { setMenuOpen(false); sincronizarTarea(); }} disabled={loading} style={{display:'block', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}>
              {loading ? 'Sincronizando...' : 'Sincronizar tarea'}
            </button>
          </div>
        )}
      </div>
      <div style={{display:'flex', gap:'16px', width:'100%', justifyContent:'flex-start', marginBottom:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas`} style={{color: '#1976d2', textDecoration: 'none', fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none'}}>&larr; Volver a tareas</Link>
      </div>
      <h2 style={{fontSize: '2rem', color: '#1976d2', marginBottom: 18, textAlign: 'center'}}>{tarea.titulo}</h2>
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
                  <th style={{padding:'6px 10px'}}>Nota</th>
                  <th style={{padding:'6px 10px'}}>Calificar</th>
                </tr>
              </thead>
              <tbody>
                {entregas.map((entrega, idx) => (
                  <tr key={idx}>
                    <td style={{padding:'6px 10px'}}>{entrega.nombre || 'Sin nombre'}</td>
                    <td style={{padding:'6px 10px'}}>{entrega.fecha_entrega}</td>
                    <td style={{padding:'6px 10px', display:'flex', alignItems:'center', gap:8}}>
                      {entrega.archivos && entrega.archivos.length > 0 ? (
                        <>
                          <a href={entrega.archivos[0].url}
                             download
                             target="_blank" rel="noopener noreferrer"
                             style={{textDecoration:'underline', color:'#1976d2'}}>
                            {entrega.archivos[0].nombre}
                          </a>
                          <button onClick={()=>window.open(entrega.archivos[0].url, '_blank')}
                                  style={{background:'#1976d2', color:'#fff', border:'none', borderRadius:4, padding:'4px 8px', cursor:'pointer'}}>
                            Descargar
                          </button>
                        </>
                      ) : 'Sin archivo'}
                    </td>
                    <td style={{padding:'6px 10px'}}>{entrega.estado}</td>
                    <td style={{padding:'6px 10px'}}>{entrega.nota != null ? entrega.nota : '-'}</td>
                    <td style={{padding:'6px 10px', display:'flex', gap:8}}>
                      {/* Botón Auto primero */}
                      <button onClick={() => {
                        const fileName = entrega.archivos[0]?.nombre || 'archivo sin nombre';
                        const hasFile = entrega.archivos && entrega.archivos.length > 0;
                        const promptText = `Por favor evalúa la entrega para la tarea "${tarea.titulo}".
Descripción de la tarea:
${tarea.descripcion}

Archivo: ${fileName}

Utiliza la rúbrica de la descripción de la tarea (si existe) pero no generes tablas ni emoticonos en la respuesta.

Proporciona:
- Una nota numérica (0-${tarea.calificacion_maxima})
- Feedback detallado.${hasFile ? '\n\nSe adjunta el fichero a evaluar.' : ''}`;
                        // Copiar prompt
                        navigator.clipboard.writeText(promptText);
                        // Abrir ChatGPT directamente y gestionar pop-up blocker
                        const chatWin = window.open('https://chat.openai.com/', '_blank');
                        if (!chatWin) {
                          alert('Se ha copiado el prompt. Por favor habilita pop-ups para abrir ChatGPT automáticamente.');
                          return;
                        }
                        chatWin.focus();
                        alert(`Prompt copiado y ChatGPT abierto en nueva pestaña.
Pasos:
1) Cambia a la pestaña de ChatGPT.
2) Pega el prompt con Ctrl+V (Windows/Linux) o Cmd+V (macOS).
3) Si hay archivo, adjúntalo.
4) Tras evaluar, haz click en "Manual" y edita la calificación y el feedback.`);
                      }} style={{background:'#1976d2', color:'#fff', padding:'4px 10px', border:'none', borderRadius:6, fontWeight:500, cursor:'pointer'}}>Auto</button>
                      {/* Enlace Manual */}
                      {entrega.link_calificar && (
                        <a href={entrega.link_calificar} target="_blank" rel="noopener noreferrer" style={{marginLeft:8, background:'#1976d2', color:'#fff', padding:'4px 10px', borderRadius:6, textDecoration:'none', fontWeight:500}}>Manual</a>
                      )}
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
