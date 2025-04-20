import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

function CursosDeCuenta() {
  const { cuentaId, usuarioId } = useParams();
  const [cursos, setCursos] = useState([]);
  const [sincronizando, setSincronizando] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [account, setAccount] = useState(null);

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

  useEffect(() => {
    fetch(`/api/usuarios/${usuarioId}/cuentas`).then(res => res.json()).then(data => {
      const acct = data.find(c => c.id === parseInt(cuentaId));
      setAccount(acct);
    });
  }, [usuarioId, cuentaId]);

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
    <div style={{position:'relative', width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', textAlign: 'center'}}>
      {/* Menú de acciones */}
      <div style={{position:'absolute', top:16, right:16}}>
        <button onClick={() => setMenuOpen(o => !o)} style={{background:'none', border:'none', cursor:'pointer', fontSize:'1.5rem'}}>⋮</button>
        {menuOpen && (
          <div style={{position:'absolute', right:0, marginTop:4, background:'#fff', border:'1px solid #ccc', borderRadius:4, boxShadow:'0 2px 6px rgba(0,0,0,0.1)'}}>
            <button onClick={() => { setMenuOpen(false); sincronizar(); }} disabled={sincronizando} style={{display:'block', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}>
              {sincronizando ? 'Sincronizando...' : 'Sincronizar cursos'}
            </button>
          </div>
        )}
      </div>
      <div style={{display: 'flex', justifyContent: 'flex-start', marginBottom: 18}}>
        <Link to={`/usuario/${usuarioId}/cuentas`} style={{ textDecoration: 'none', color: '#1976d2', fontWeight: 500, padding: '10px 20px', borderRadius: 5, background: '#e3eefd', border: 'none' }}>
          &larr; Volver a cuentas
        </Link>
      </div>
      <h2 style={{color: '#1976d2', fontSize: '2rem', marginBottom: 18}}>{account ? `Cursos de la cuenta ${account.usuario_moodle}` : 'Cursos de la cuenta'}</h2>
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
