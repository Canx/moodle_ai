import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

function TareaIndividual() {
  const { tareaId, cursoId, cuentaId, usuarioId } = useParams();
  const [tarea, setTarea] = useState(null);
  const [desc, setDesc] = useState(null);
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
    <div>
      <h2>{tarea.titulo}</h2>
      <button onClick={sincronizarDescripcion} disabled={loading} style={{ marginBottom: "10px" }}>
        {loading ? "Sincronizando..." : "Sincronizar descripción"}
      </button>
      {error && <div style={{ color: "red" }}>{error}</div>}
      {desc && <div style={{ marginTop: "10px" }} dangerouslySetInnerHTML={{ __html: desc }} />}
      <div style={{marginTop:'20px'}}>
        <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${cursoId}/tareas`}>&larr; Volver a tareas</Link>
      </div>
    </div>
  );
}

export default TareaIndividual;
