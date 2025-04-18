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
    <div style={{width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', textAlign: 'center'}}>
      <div style={{display: 'flex', justifyContent: 'flex-end', gap: 12, marginBottom: 18}}>
        <button onClick={sincronizar} disabled={sincronizando} style={{ background: '#e3eefd', color: '#1976d2', border: 'none', borderRadius: 6, padding: '8px 22px', fontWeight: 600, fontSize: '1.05rem', cursor: 'pointer', transition: 'background 0.2s' }}
          onMouseOver={e => e.currentTarget.style.background='#d1e2fc'}
          onMouseOut={e => e.currentTarget.style.background='#e3eefd'}>
          {sincronizando ? 'Sincronizando...' : 'Sincronizar'}
        </button>
        <button onClick={() => navigate(-1)} style={{ background: '#e3eefd', color: '#1976d2', border: 'none', borderRadius: 6, padding: '8px 22px', fontWeight: 600, fontSize: '1.05rem', cursor: 'pointer', transition: 'background 0.2s' }}
          onMouseOver={e => e.currentTarget.style.background='#d1e2fc'}
          onMouseOut={e => e.currentTarget.style.background='#e3eefd'}>
          Atrás
        </button>
      </div>
      <h2 style={{color: '#1976d2', fontSize: '2rem', marginBottom: 18}}>Cursos sincronizados</h2>
      <div style={{display: 'flex', flexDirection: 'column', gap: 22, alignItems: 'center', width: '100%'}}>
        {cursos.length === 0 && (
          <div style={{width: '100%', background: '#f7fafd', borderRadius: 12, boxShadow: '0 2px 8px #0001', padding: '32px 0', color: '#888', fontSize: '1.13rem', textAlign: 'center'}}>
            No hay cursos sincronizados.
          </div>
        )}
        {cursos.map((curso) => (
          <div key={curso.id || curso.nombre} style={{width: '100%', background: '#fff', borderRadius: 14, boxShadow: '0 2px 12px #0002', padding: '28px 26px', display: 'flex', alignItems: 'center', justifyContent: 'flex-start'}}>
            <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${curso.id}/tareas`} style={{ color: '#1976d2', textDecoration: 'none', fontWeight: 600, fontSize: '1.25rem', letterSpacing: '.01em' }}>
              {curso.nombre}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CursosDeCuenta;
