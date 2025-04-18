import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

function TareaIndividual() {
  const { tareaId, cursoId, cuentaId, usuarioId } = useParams();
  const [tarea, setTarea] = useState(null);
  const [desc, setDesc] = useState(null);

  // Mostrar la descripción local al cargar la tarea si existe
  useEffect(() => {
    if (tarea && tarea.descripcion) {
      setDesc(tarea.descripcion);
    }
  }, [tarea]);
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

  const sincronizarDescripcion = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tareas/${tareaId}/descripcion`);
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

  if (error) return <div style={{color:'red'}}>{error}</div>;
  if (!tarea) return <div>Cargando tarea...</div>;

  return (
    <div style={{width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', display: 'flex', flexDirection: 'column'}}>
      {/* Breadcrumb visual */}
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
      <button onClick={sincronizarDescripcion} disabled={loading} style={{ background: '#1976d2', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 22px', fontWeight: 600, fontSize: '1rem', cursor: loading ? 'not-allowed' : 'pointer', marginBottom: '18px', boxShadow: loading ? 'none' : '0 2px 6px #1976d233', opacity: loading ? 0.6 : 1, transition: 'opacity 0.2s' }}>
        {loading ? "Sincronizando..." : "Sincronizar"}
      </button>
      {error && <div style={{ color: "#d32f2f", background: '#fff0f0', borderRadius: 6, padding: '8px 14px', marginBottom: 10 }}>{error}</div>}
      {desc && <div style={{ marginTop: "10px", width: '100%', color: '#444', fontSize: '1.08rem', background: '#f7f7fa', borderRadius: 8, padding: 18 }} dangerouslySetInnerHTML={{ __html: desc }} />}
    </div>
  );
}

export default TareaIndividual;
