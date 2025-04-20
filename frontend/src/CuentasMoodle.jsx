import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";

function CuentasMoodle() {
  const { usuarioId } = useParams();
  const [cuentas, setCuentas] = useState([]);
  const [moodleUrl, setMoodleUrl] = useState("");
  const [usuarioMoodle, setUsuarioMoodle] = useState("");
  const [contrasenaMoodle, setContrasenaMoodle] = useState("");
  const [editId, setEditId] = useState(null);
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();

  const obtenerCuentas = async () => {
    const response = await fetch(`/api/usuarios/${usuarioId}/cuentas`);
    const data = await response.json();
    setCuentas(data);
  };

  const limpiarFormulario = () => {
    setMoodleUrl("");
    setUsuarioMoodle("");
    setContrasenaMoodle("");
    setEditId(null);
  };

  const agregarOEditarCuenta = async () => {
    if (editId) {
      const response = await fetch(`/api/usuarios/${usuarioId}/cuentas/${editId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          moodle_url: moodleUrl,
          usuario_moodle: usuarioMoodle,
          contrasena_moodle: contrasenaMoodle,
        }),
      });
      if (response.ok) {
        obtenerCuentas();
        limpiarFormulario();
      }
    } else {
      const response = await fetch(`/api/usuarios/${usuarioId}/cuentas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          moodle_url: moodleUrl,
          usuario_moodle: usuarioMoodle,
          contrasena_moodle: contrasenaMoodle,
        }),
      });
      if (response.ok) {
        obtenerCuentas();
        limpiarFormulario();
      }
    }
  };

  const borrarCuenta = async (id) => {
    const response = await fetch(`/api/usuarios/${usuarioId}/cuentas/${id}`, {
      method: "DELETE",
    });
    if (response.ok) {
      obtenerCuentas();
    }
  };

  const editarCuenta = (cuenta) => {
    setEditId(cuenta.id);
    setMoodleUrl(cuenta.moodle_url);
    setUsuarioMoodle(cuenta.usuario_moodle);
    setContrasenaMoodle("");
  };

  useEffect(() => {
    obtenerCuentas();
  }, []);

  return (
    <div style={{position:'relative', width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', textAlign: 'center'}}>
      {/* Menú superior */}
      <div style={{position:'absolute', top:16, right:16}}>
        <button onClick={() => setMenuOpen(o => !o)} style={{background:'none', border:'none', cursor:'pointer', fontSize:'1.5rem'}}>⋮</button>
        {menuOpen && (
          <div style={{position:'absolute', top:36, right:0, background:'#fff', border:'1px solid #ccc', borderRadius:4, boxShadow:'0 2px 6px rgba(0,0,0,0.1)', zIndex:10}}>
            <Link to={`/usuario/${usuarioId}/cuentas/new`} style={{display:'block', padding:'8px 12px', background:'none', border:'none', width:'150px', textAlign:'left', cursor:'pointer'}}>Agregar cuenta</Link>
          </div>
        )}
      </div>
      <h2 style={{color: '#1976d2', fontSize: '2rem', marginBottom: 18}}>Mis Cuentas de Moodle</h2>
      <div style={{marginBottom: 32}}>
        {cuentas.length === 0 ? (
          <div style={{color:'#888', fontSize:'1.1rem', margin:'18px 0'}}>No tienes cuentas de Moodle registradas.</div>
        ) : (
          <div style={{display:'flex', flexDirection:'column', gap: '18px'}}>
            {cuentas.map((cuenta) => (
              <div key={cuenta.id} style={{position:'relative', background:'#f7faff', borderRadius: 14, boxShadow:'0 1px 6px #0001', padding:'20px 24px', display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap'}}>
                {/* Tarjeta clicable */}
                <div onClick={() => navigate(`/usuario/${usuarioId}/cuentas/${cuenta.id}/cursos`)} style={{flex:1, cursor:'pointer', display:'flex', alignItems:'center'}}>
                  <span style={{marginRight:10, fontWeight:600, color:'#1976d2', fontSize:'1.1rem'}}>{cuenta.moodle_url}</span>
                  <span style={{color:'#444', fontWeight:400}}>{cuenta.usuario_moodle}</span>
                </div>
                {/* Menú de acciones */}
                <div style={{position:'relative'}}>
                  <button onClick={() => setMenuOpenId(menuOpenId === cuenta.id ? null : cuenta.id)} style={{background:'none', border:'none', cursor:'pointer', fontSize:'1.5rem'}}>⋮</button>
                  {menuOpenId === cuenta.id && (
                    <div style={{position:'absolute', right:0, marginTop:4, background:'#fff', border:'1px solid #ccc', borderRadius:4, boxShadow:'0 2px 6px rgba(0,0,0,0.1)', zIndex:10}}>
                      <button onClick={() => { editarCuenta(cuenta); setMenuOpenId(null); }} style={{display:'block', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}>Editar</button>
                      <button onClick={() => { borrarCuenta(cuenta.id); setMenuOpenId(null); }} style={{display:'block', padding:'8px 12px', background:'none', border:'none', width:'100%', textAlign:'left', cursor:'pointer'}}>Borrar</button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default CuentasMoodle;