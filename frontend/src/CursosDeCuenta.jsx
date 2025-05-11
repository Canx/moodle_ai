import React, { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { Spinner } from "react-bootstrap";

function CursosDeCuenta() {
  const { cuentaId, usuarioId } = useParams();
  const [cursos, setCursos] = useState([]);
  const [sincronizando, setSincronizando] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [account, setAccount] = useState(null);
  const [mostrarOcultos, setMostrarOcultos] = useState(false);
  const [cursosOcultos, setCursosOcultos] = useState([]);
  const [openCourseMenuId, setOpenCourseMenuId] = useState(null);
  const [unhidingCourseId, setUnhidingCourseId] = useState(null);
  const [error, setError] = useState(null);
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

  useEffect(() => {
    fetch(`/api/usuarios/${usuarioId}/cuentas`).then(res => res.json()).then(data => {
      const acct = data.find(c => c.id === parseInt(cuentaId));
      setAccount(acct);
    });
  }, [usuarioId, cuentaId]);

  const sincronizar = async () => {
    setSincronizando(true);
    setError(null);
    try {
      const res = await fetch(`/api/cuentas/${cuentaId}/sincronizar_cursos`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        if (res.status === 401) {
          setError("Las credenciales de Moodle son incorrectas. Por favor, edita la cuenta para corregirlas.");
          setSincronizando(false);
          setMenuOpen(false);
          return;
        }
        throw new Error(data.detail || "Error desconocido al sincronizar");
      }
    } catch (e) {
      setError(e.message);
      setSincronizando(false);
      setMenuOpen(false);
      return;
    }

    // Polling de estado
    const checkEstado = async () => {
      const res = await fetch(`/api/cuentas/${cuentaId}/sincronizacion`);
      const data = await res.json();
      if (data.estado === "sincronizando") {
        setTimeout(checkEstado, 2000);
      } else if (data.estado.startsWith("error_credenciales:")) {
        setError("Las credenciales de Moodle son incorrectas. Por favor, edita la cuenta para corregirlas.");
        setSincronizando(false);
        setMenuOpen(false);
      } else if (data.estado.startsWith("error:")) {
        setError(data.estado.substring(6));
        setSincronizando(false);
        setMenuOpen(false);
      } else {
        setSincronizando(false);
        setMenuOpen(false);
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
            <button onClick={() => sincronizar()} disabled={sincronizando} style={{display:'flex', alignItems:'center', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}>
              {sincronizando ? (
                <><Spinner animation="border" size="sm" className="me-2" />Sincronizando...</>
              ) : (
                'Sincronizar cursos'
              )}
            </button>
            <button onClick={() => navigate(`/usuario/${usuarioId}/cuentas/${cuentaId}/edit`)} style={{display:'flex', alignItems:'center', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}>
              Editar cuenta
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
      {error && (
        <div style={{background: '#fdecea', color: '#d32f2f', padding: '12px 20px', borderRadius: 8, marginBottom: 20, textAlign: 'left'}}>
          {error}
        </div>
      )}
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '22px', width: '100%'}}>
        {cursos.length === 0 && (
          <div style={{width: '100%', background: '#f7fafd', borderRadius: 12, boxShadow: '0 2px 8px #0001', padding: '32px 0', color: '#888', fontSize: '1.13rem', textAlign: 'center'}}>
            No hay cursos sincronizados.
          </div>
        )}
        {cursos.map(curso => (
          <div key={curso.id} style={{position: 'relative'}}>
            <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${curso.id}/tareas`} style={{textDecoration: 'none', display: 'block'}}>
              <div style={{width: '100%', background: '#fff', borderRadius: 14, boxShadow: '0 2px 12px #0002', padding: '28px 26px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer'}}>
                <span style={{ color: '#1976d2', fontWeight: 600, fontSize: '1.25rem', letterSpacing: '.01em', textAlign: 'center', whiteSpace: 'normal', wordBreak: 'break-word' }}>
                  {curso.nombre}
                </span>
              </div>
            </Link>
            <button onClick={() => setOpenCourseMenuId(openCourseMenuId === curso.id ? null : curso.id)} style={{position: 'absolute', top: 8, right: 8, background: 'transparent', border: 'none', fontSize: '1.2rem', cursor: 'pointer'}}>⋮</button>
            {openCourseMenuId === curso.id && (
              <div style={{position: 'absolute', top: 28, right: 8, background: '#fff', border: '1px solid #ccc', borderRadius: 4, boxShadow: '0 2px 6px rgba(0,0,0,0.1)', zIndex: 10}}>
                <div onClick={async () => {
                  await fetch(`/api/cursos/${curso.id}/ocultar`, { method: 'POST' });
                  const res = await fetch(`/api/cuentas/${cuentaId}/cursos`);
                  if (res.ok) setCursos(await res.json());
                  setOpenCourseMenuId(null);
                }} style={{padding: '6px 12px', cursor: 'pointer', whiteSpace: 'nowrap'}}>Ocultar</div>
              </div>
            )}
          </div>
        ))}
      </div>
      {/* Sección de cursos ocultos */}
      <div style={{ marginTop: 20, textAlign: 'center' }}>
        <button onClick={async () => {
          if (!mostrarOcultos) {
            const resOc = await fetch(`/api/cuentas/${cuentaId}/cursos/ocultos`);
            if (resOc.ok) setCursosOcultos(await resOc.json());
          }
          setMostrarOcultos(o => !o);
        }} style={{ marginBottom: 10, background: '#888', color: '#fff', padding: '10px 20px', border: 'none', borderRadius: 5, cursor: 'pointer' }}>
          {mostrarOcultos ? 'Ocultar cursos ocultos' : 'Ver cursos ocultos'}
        </button>
        {mostrarOcultos && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '22px', width: '100%' }}>
            {cursosOcultos.length === 0 && <div>No hay cursos ocultos.</div>}
            {cursosOcultos.map(curso => (
              <div key={curso.id} style={{ background: '#fff', borderRadius: 14, boxShadow: '0 2px 12px #0002', padding: '28px 26px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: '160px' }}>
                <Link to={`/usuario/${usuarioId}/cuentas/${cuentaId}/cursos/${curso.id}/tareas`} style={{ textDecoration: 'none', color: '#1976d2', fontWeight: 600, fontSize: '1.25rem', letterSpacing: '.01em', textAlign: 'center', whiteSpace: 'normal', wordBreak: 'break-word' }}>
                  {curso.nombre}
                </Link>
                <button
                  onClick={async () => {
                    setUnhidingCourseId(curso.id);
                    await fetch(`/api/cursos/${curso.id}/mostrar`, { method: 'POST' });
                    const resOc2 = await fetch(`/api/cuentas/${cuentaId}/cursos/ocultos`);
                    if (resOc2.ok) setCursosOcultos(await resOc2.json());
                    setUnhidingCourseId(null);
                  }}
                  disabled={unhidingCourseId === curso.id}
                  style={{ marginTop: 8, background: '#27ae60', color: '#fff', border: 'none', borderRadius: 5, padding: '6px 10px', cursor: 'pointer' }}
                >
                  {unhidingCourseId === curso.id ? (<><Spinner animation="border" size="sm" className="me-2" />Mostrar...</>) : 'Mostrar'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default CursosDeCuenta;
