import React from "react";
import { Link, useParams } from "react-router-dom";
import LLMConfig from "./LLMConfig";

function Usuario() {
  const { usuarioId } = useParams();
  const [nombre, setNombre] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    const fetchNombre = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/usuarios/${usuarioId}`);
        if (res.ok) {
          const data = await res.json();
          setNombre(data.nombre || "");
        } else {
          setError("No se pudo obtener el nombre de usuario");
        }
      } catch (e) {
        setError("Error de red al obtener usuario");
      }
      setLoading(false);
    };
    fetchNombre();
  }, [usuarioId]);

  return (
    <div style={{width: '95%', margin: '60px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '48px 36px', textAlign: 'center'}}>
      {loading ? (
        <h2 style={{color: '#1976d2', fontSize: '2.2rem', marginBottom: 18, fontWeight: 700}}>Cargando...</h2>
      ) : error ? (
        <h2 style={{color: '#d32f2f', fontSize: '1.5rem', marginBottom: 18, fontWeight: 600}}>{error}</h2>
      ) : (
        <h2 style={{color: '#1976d2', fontSize: '2.2rem', marginBottom: 18, fontWeight: 700}}>Bienvenido, <span style={{fontWeight:800}}>{nombre}</span></h2>
      )}
      <div style={{marginTop: 32}}>
        <div style={{display:'flex', justifyContent:'center', gap: 24, marginBottom: 48}}>
          <Link to={`/usuario/${usuarioId}/cuentas`} style={{background: '#e3eefd', color: '#1976d2', border: 'none', borderRadius: 6, padding: '14px 32px', fontWeight: 600, fontSize: '1.12rem', textDecoration: 'none', transition: 'background 0.2s'}} onMouseOver={e => e.currentTarget.style.background='#d1e2fc'} onMouseOut={e => e.currentTarget.style.background='#e3eefd'}>
            Gestionar Cuentas de Moodle
          </Link>
          <Link to="/" style={{background: '#e3eefd', color: '#1976d2', border: 'none', borderRadius: 6, padding: '14px 32px', fontWeight: 600, fontSize: '1.12rem', textDecoration: 'none', transition: 'background 0.2s'}} onMouseOver={e => e.currentTarget.style.background='#d1e2fc'} onMouseOut={e => e.currentTarget.style.background='#e3eefd'}>
            Volver al Inicio
          </Link>
        </div>          <div style={{borderTop: '1px solid #eee', paddingTop: 32}}>
          <LLMConfig usuarioId={usuarioId} />
        </div>
      </div>
    </div>
  );
}

export default Usuario;