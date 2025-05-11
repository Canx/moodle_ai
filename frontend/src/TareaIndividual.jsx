import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Spinner, Modal, Button } from 'react-bootstrap';

function TareaIndividual() {
  const { tareaId, cursoId, cuentaId, usuarioId } = useParams();
  const [tarea, setTarea] = useState(null);
  const [desc, setDesc] = useState(null);
  const [entregas, setEntregas] = useState([]);
  const [descOpen, setDescOpen] = useState(false);
  const [entregasOpen, setEntregasOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showTextoModal, setShowTextoModal] = useState(false);
  const [selectedTexto, setSelectedTexto] = useState("");
  const [syncStatus, setSyncStatus] = useState({estado:'no_iniciado', fecha: null});
  const [error, setError] = useState(null);
  const [generalPrompt, setGeneralPrompt] = useState('');
  const [subPrompt, setSubPrompt] = useState('');
  const navigate = useNavigate();
  const [guideOpen, setGuideOpen] = useState(false);
  const [defaultLLM, setDefaultLLM] = useState(null);

  // Cargar la configuración de LLM del usuario
  useEffect(() => {
    if (usuarioId) {
      fetch(`/api/usuarios/${usuarioId}/llm_config`)
        .then(res => res.json())
        .then(data => setDefaultLLM(data))
        .catch(console.error);
    }
  }, [usuarioId]);

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

  // Carga del prompt general
  useEffect(() => {
    fetch('/prompts/general_evaluate.md')
      .then(res => res.text())
      .then(setGeneralPrompt)
      .catch(console.error);
  }, []);

  // Carga de sub-prompt según tipo de calificación
  useEffect(() => {
    if (!tarea) return;
    let file;
    if (tarea.tipo_calificacion === 'guide') file = '/prompts/sub_guide.md';
    else if (tarea.tipo_calificacion === 'rubric') file = '/prompts/sub_rubric.md';
    else file = '/prompts/sub_simple.md';
    fetch(file)
      .then(res => res.text())
      .then(setSubPrompt)
      .catch(console.error);
  }, [tarea]);

  // Iniciar sincronización en background y mostrar estado
  const sincronizarTarea = () => {
    setSyncStatus({ estado: 'sincronizando', fecha: new Date().toISOString() });
    fetch(`/api/tareas/${tareaId}/sincronizar`, { method: "POST" })
      .catch(() => {
        setSyncStatus({ estado: 'error', fecha: new Date().toISOString() });
      });
  };

  // Polling de estado tras iniciar sincronización
  useEffect(() => {
    if (syncStatus.estado === 'sincronizando') {
      const interval = setInterval(async () => {
        try {
          const res = await fetch(`/api/tareas/${tareaId}`);
          if (res.ok) {
            const data = await res.json();
            setSyncStatus({ estado: data.estado, fecha: data.fecha_sincronizacion });
            if (data.estado !== 'sincronizando') {
              setDesc(data.descripcion);
              const entregasRes = await fetch(`/api/tareas/${tareaId}/entregas_pendientes`);
              if (entregasRes.ok) setEntregas(await entregasRes.json());
              clearInterval(interval);
            }
          }
        } catch {}
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [syncStatus.estado, tareaId]);

  if (error) return <div style={{color:'red'}}>{error}</div>;
  if (!tarea) return <div>Cargando tarea...</div>;

  return (
    <div style={{position: 'relative', width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', display: 'flex', flexDirection: 'column'}}>
      {syncStatus.estado !== 'no_iniciado' && (
        <div style={{ marginBottom: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
          {syncStatus.estado === 'sincronizando' && <Spinner animation="border" size="sm" className="me-2" />}
          <span>Sincronización: {syncStatus.estado}</span>
          {syncStatus.fecha && <small>({new Date(syncStatus.fecha).toLocaleTimeString()})</small>}
        </div>
      )}
      {/* Menú de acciones */}
      <div style={{position: 'absolute', top: 16, right: 16}}>
        <button onClick={() => setMenuOpen(o => !o)} style={{background:'none', border:'none', cursor:'pointer', fontSize:'1.5rem'}}>⋮</button>
        {menuOpen && (
          <div style={{position:'absolute', right:0, marginTop:4, background:'#fff', border:'1px solid #ccc', borderRadius:4, boxShadow:'0 2px 6px rgba(0,0,0,0.2)'}}>
            <button
              onClick={() => { setMenuOpen(false); sincronizarTarea(); }}
              disabled={syncStatus.estado === 'sincronizando'}
              style={{display:'flex', alignItems:'center', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}
            >
              {syncStatus.estado === 'sincronizando'
                ? (<><Spinner animation="border" size="sm" className="me-2" />Sincronizando...</>)
                : 'Sincronizar tarea'}
            </button>
          </div>
        )}
      </div>
      <div style={{display:'flex', gap:'16px', width:'100%', justifyContent:'flex-start', marginBottom:'18px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas`} style={{color: '#1976d2', textDecoration: 'none', fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none'}}>&larr; Volver a tareas</Link>
      </div>
      <h2 style={{fontSize: '2rem', color: '#1976d2', marginBottom: 18, textAlign: 'center'}}>
        <a
          href={tarea.link_tarea}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: '#1976d2', textDecoration: 'none' }}
        >
          {tarea.titulo}
        </a>
      </h2>
      <p style={{textAlign: 'center', marginBottom: '6px', fontSize: '1rem'}}>
        Calificación máxima: <strong>{tarea.calificacion_maxima ?? '-'}</strong>
      </p>
      <p style={{textAlign: 'center', marginBottom: '18px', fontSize: '1rem'}}>
        Tipo de evaluación: <strong>{tarea.tipo_calificacion || 'none'}</strong>
      </p>
      {/* Métricas de entregas vs total y evaluaciones vs entregadas */}
      {entregas && (
        (() => {
          const totalCount = entregas.length;
          const deliveredCount = entregas.filter(e =>
            e.estado?.toLowerCase().startsWith('enviado') || e.estado?.toLowerCase().startsWith('pendiente')
          ).length;
          const evaluatedCount = entregas.filter(e => e.nota != null).length;
          return (
            <div style={{marginBottom: '18px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px'}}>
              <span style={{background: '#2196f3', color: '#fff', borderRadius: 5, padding: '4px 8px', fontWeight: 600}}>
                Total: {totalCount}
              </span>
              <span style={{background: '#ffc107', color: '#000', borderRadius: 5, padding: '4px 8px', fontWeight: 600}}>
                Entregadas: {deliveredCount}
              </span>
              <span style={{background: '#4caf50', color: '#fff', borderRadius: 5, padding: '4px 8px', fontWeight: 600}}>
                Evaluadas: {evaluatedCount}
              </span>
            </div>
          );
        })()
      )}
      {(tarea.tipo_calificacion === 'guide' || tarea.tipo_calificacion === 'rubric') && (
        <div style={{marginBottom: '18px'}}>
          <button onClick={() => setGuideOpen(o => !o)} style={{background: '#1976d2', color: '#fff', border: 'none', borderRadius: 7, padding: '7px 16px', fontWeight: 600, fontSize: '1rem', cursor: 'pointer', marginBottom: 6}}>
            {guideOpen ? 'Ocultar guía de evaluación' : 'Mostrar guía de evaluación'}
          </button>
          {guideOpen && tarea.detalles_calificacion && (
            <div style={{marginTop: '10px', width: '100%', color: '#444', fontSize: '1.08rem', background: '#f7f7fa', borderRadius: 8, padding: 18}} dangerouslySetInnerHTML={{ __html: tarea.detalles_calificacion }} />
          )}
        </div>
      )}
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
                  <th style={{padding:'6px 10px'}}>Texto</th>
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
                        </>
                      ) : 'Sin archivo'}
                    </td>
                    <td style={{padding:'6px 10px'}}>
                      {entrega.texto ? (
                        <Button variant="outline-primary" size="sm" onClick={() => { setSelectedTexto(entrega.texto); setShowTextoModal(true); }}>
                          Ver
                        </Button>
                      ) : 'Sin texto'}
                    </td>
                    <td style={{padding:'6px 10px'}}>{entrega.estado}</td>
                    <td style={{padding:'6px 10px'}}>{entrega.nota != null ? entrega.nota : '-'}</td>
                    <td style={{padding:'6px 10px', display:'flex', gap:8}}>
                      {/* Botón Auto primero */}
                      <button onClick={() => {
                        const fileName = entrega.archivos[0]?.nombre || 'archivo sin nombre';
                        const hasFile = entrega.archivos && entrega.archivos.length > 0;
                        const textoContent = entrega.texto || '';
                        // Secciones dinámicas de entrega
                        const fileSection = hasFile ? `Archivo: ${fileName}\n\n` : '';
                        const textoSection = textoContent ? `Texto: ${textoContent}\n\n` : '';
                        // Convertir descripción HTML a texto plano
                        const parser = new DOMParser();
                        const plainDesc = desc ? parser.parseFromString(desc, 'text/html').body.textContent.trim() : '';
                        // Generar prompt combinando templates
                        let prompt = generalPrompt
                          .replace('{nombre_alumno}', entrega.nombre || '')
                          .replace('{tarea_titulo}', tarea.titulo)
                          .replace('{descripcion}', plainDesc)
                          .replace('{file_section}', fileSection)
                          .replace('{texto_section}', textoSection);
                        if (subPrompt) {
                          const sub = subPrompt
                            .replace('{calificacion_maxima}', tarea.calificacion_maxima)
                            .replace('{detalles_calificacion}', tarea.detalles_calificacion || '')
                            .replace('{adjuntar_archivo}', hasFile ? '\n\nSe adjunta el fichero a evaluar.' : '');
                          prompt = `${prompt}\n${sub}`;
                        }
                        navigator.clipboard.writeText(prompt);
                        alert(`Prompt copiado y ${defaultLLM?.nombre || 'el LLM'} se abrirá en nueva pestaña a continuación.
                          Pasos:
                          1) Cambia a la pestaña de ${defaultLLM?.nombre || 'el LLM'}.
                          2) Pega el prompt con Ctrl+V (Windows/Linux) o Cmd+V (macOS).
                          3) Si hay archivo, adjúntalo.
                          4) Tras evaluar, haz click en "Manual" y edita la calificación y el feedback.`);
                        // Abrir ChatGPT directamente y gestionar pop-up blocker
                        const url = defaultLLM?.url_template || 'https://chat.openai.com/';
                        const chatWin = window.open(url, '_blank');
                        if (!chatWin) {
                          alert('Se ha copiado el prompt. Por favor habilita pop-ups para abrir el LLM automáticamente.');
                          return;
                        }
                        chatWin.focus();
                        
                      }} style={{background:'#1976d2', color:'#fff', padding:'4px 10px', border:'none', borderRadius:6, fontWeight:500, cursor:'pointer'}}>
                        {defaultLLM ? defaultLLM.nombre.split(' ')[0] : 'Auto'}
                      </button>
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
      {/* Modal para mostrar texto largo */}
      <Modal show={showTextoModal} onHide={() => setShowTextoModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>Texto de entrega</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{selectedTexto}</pre>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowTextoModal(false)}>Cerrar</Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}

export default TareaIndividual;
