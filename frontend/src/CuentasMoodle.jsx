import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

function CuentasMoodle() {
  const { usuarioId } = useParams();
  const [cuentas, setCuentas] = useState([]);
  const [moodleUrl, setMoodleUrl] = useState("");
  const [usuarioMoodle, setUsuarioMoodle] = useState("");
  const [contrasenaMoodle, setContrasenaMoodle] = useState("");
  const [editId, setEditId] = useState(null);
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
    <div style={{width: '95%', margin: '40px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '36px 30px 40px 30px', textAlign: 'center'}}>
      <h2 style={{color: '#1976d2', fontSize: '2rem', marginBottom: 18}}>Mis Cuentas de Moodle</h2>
      <div style={{marginBottom: 32}}>
        {cuentas.length === 0 ? (
          <div style={{color:'#888', fontSize:'1.1rem', margin:'18px 0'}}>No tienes cuentas de Moodle registradas.</div>
        ) : (
          <div style={{display:'flex', flexDirection:'column', gap: '18px'}}>
            {cuentas.map((cuenta) => (
              <div key={cuenta.id} style={{background:'#f7faff', borderRadius: 14, boxShadow:'0 1px 6px #0001', padding:'20px 24px', display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap'}}>
                <div style={{fontWeight:600, color:'#1976d2', fontSize:'1.1rem'}}>
                  <span style={{marginRight:10}}>{cuenta.moodle_url}</span>
                  <span style={{color:'#444', fontWeight:400}}>{cuenta.usuario_moodle}</span>
                </div>
                <div style={{display:'flex', gap: '8px'}}>
                  <button onClick={() => editarCuenta(cuenta)} style={{background:'#e3eefd', color:'#1976d2', border:'none', borderRadius:6, padding:'8px 16px', fontWeight:600, cursor:'pointer', transition:'background 0.2s'}} onMouseOver={e=>e.currentTarget.style.background='#d1e2fc'} onMouseOut={e=>e.currentTarget.style.background='#e3eefd'}>
                    Editar
                  </button>
                  <button onClick={() => borrarCuenta(cuenta.id)} style={{background:'#fff0f0', color:'#d32f2f', border:'none', borderRadius:6, padding:'8px 16px', fontWeight:600, cursor:'pointer', transition:'background 0.2s'}} onMouseOver={e=>e.currentTarget.style.background='#f8d6d6'} onMouseOut={e=>e.currentTarget.style.background='#fff0f0'}>
                    Borrar
                  </button>
                  <button onClick={() => navigate(`/usuario/${usuarioId}/cuentas/${cuenta.id}/cursos`)} style={{background:'#1976d2', color:'#fff', border:'none', borderRadius:6, padding:'8px 16px', fontWeight:600, cursor:'pointer', transition:'background 0.2s'}} onMouseOver={e=>e.currentTarget.style.background='#125fa2'} onMouseOut={e=>e.currentTarget.style.background='#1976d2'}>
                    Ver
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <div style={{background:'#f7faff', borderRadius:14, boxShadow:'0 1px 6px #0001', padding:'28px 22px', maxWidth:480, margin:'0 auto'}}>
        <h3 style={{color:'#1976d2', fontWeight:700, fontSize:'1.25rem', marginBottom:16}}>{editId ? "Editar Cuenta" : "Agregar Cuenta"}</h3>
        <input
          type="text"
          placeholder="URL de Moodle"
          value={moodleUrl}
          onChange={(e) => setMoodleUrl(e.target.value)}
          style={{width:'100%', padding:'12px 14px', marginBottom:12, borderRadius:7, border:'1px solid #b9c6e0', fontSize:'1rem', outline:'none', boxSizing:'border-box'}}
        />
        <input
          type="text"
          placeholder="Usuario de Moodle"
          value={usuarioMoodle}
          onChange={(e) => setUsuarioMoodle(e.target.value)}
          style={{width:'100%', padding:'12px 14px', marginBottom:12, borderRadius:7, border:'1px solid #b9c6e0', fontSize:'1rem', outline:'none', boxSizing:'border-box'}}
        />
        <input
          type="password"
          placeholder="Contraseña de Moodle"
          value={contrasenaMoodle}
          onChange={(e) => setContrasenaMoodle(e.target.value)}
          style={{width:'100%', padding:'12px 14px', marginBottom:16, borderRadius:7, border:'1px solid #b9c6e0', fontSize:'1rem', outline:'none', boxSizing:'border-box'}}
        />
        <button onClick={agregarOEditarCuenta} style={{background:'#1976d2', color:'#fff', border:'none', borderRadius:7, padding:'12px 24px', fontWeight:600, fontSize:'1rem', cursor:'pointer', boxShadow:'0 2px 8px #0001', transition:'background 0.2s'}} onMouseOver={e=>e.currentTarget.style.background='#125fa2'} onMouseOut={e=>e.currentTarget.style.background='#1976d2'}>
          {editId ? "Guardar Cambios" : "Agregar Cuenta"}
        </button>
        {editId && (
          <button onClick={limpiarFormulario} style={{ marginLeft: "10px", background:'#e3eefd', color:'#1976d2', border:'none', borderRadius:7, padding:'12px 24px', fontWeight:600, fontSize:'1rem', cursor:'pointer', transition:'background 0.2s'}} onMouseOver={e=>e.currentTarget.style.background='#d1e2fc'} onMouseOut={e=>e.currentTarget.style.background='#e3eefd'}>
            Cancelar
          </button>
        )}
      </div>
    </div>
  );
}

export default CuentasMoodle;