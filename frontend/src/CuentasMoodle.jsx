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
      <ul>
        {cuentas.map((cuenta) => (
          <li key={cuenta.id}>
            {cuenta.moodle_url} - {cuenta.usuario_moodle}
            <button onClick={() => editarCuenta(cuenta)} style={{ marginLeft: "10px" }}>
              Editar
            </button>
            <button onClick={() => borrarCuenta(cuenta.id)} style={{ marginLeft: "5px", color: "red" }}>
              Borrar
            </button>
            <button onClick={() => navigate(`/usuario/${usuarioId}/cuentas/${cuenta.id}/cursos`)} style={{ marginLeft: "5px" }}>
              Ver
            </button>
          </li>
        ))}
      </ul>
      <h3>{editId ? "Editar Cuenta" : "Agregar Cuenta"}</h3>
      <input
        type="text"
        placeholder="URL de Moodle"
        value={moodleUrl}
        onChange={(e) => setMoodleUrl(e.target.value)}
      />
      <input
        type="text"
        placeholder="Usuario de Moodle"
        value={usuarioMoodle}
        onChange={(e) => setUsuarioMoodle(e.target.value)}
      />
      <input
        type="password"
        placeholder="Contraseña de Moodle"
        value={contrasenaMoodle}
        onChange={(e) => setContrasenaMoodle(e.target.value)}
      />
      <button onClick={agregarOEditarCuenta}>
        {editId ? "Guardar Cambios" : "Agregar Cuenta"}
      </button>
      {editId && (
        <button onClick={limpiarFormulario} style={{ marginLeft: "10px" }}>
          Cancelar
        </button>
      )}
    </div>
  );
}

export default CuentasMoodle;