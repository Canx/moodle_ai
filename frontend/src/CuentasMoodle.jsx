import React, { useState, useEffect } from "react";

function CuentasMoodle({ usuarioId }) {
  const [cuentas, setCuentas] = useState([]);
  const [moodleUrl, setMoodleUrl] = useState("");
  const [usuarioMoodle, setUsuarioMoodle] = useState("");
  const [contrasenaMoodle, setContrasenaMoodle] = useState("");

  const obtenerCuentas = async () => {
    const response = await fetch(`/api/usuarios/${usuarioId}/cuentas`);
    const data = await response.json();
    setCuentas(data);
  };

  const agregarCuenta = async () => {
    const response = await fetch(`/api/usuarios/${usuarioId}/cuentas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ moodle_url: moodleUrl, usuario_moodle: usuarioMoodle, contrasena_moodle: contrasenaMoodle }),
    });
    if (response.ok) {
      obtenerCuentas();
    }
  };

  useEffect(() => {
    obtenerCuentas();
  }, []);

  return (
    <div>
      <h2>Mis Cuentas de Moodle</h2>
      <ul>
        {cuentas.map((cuenta) => (
          <li key={cuenta.id}>{cuenta.moodle_url} - {cuenta.usuario_moodle}</li>
        ))}
      </ul>
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
      <button onClick={agregarCuenta}>Agregar Cuenta</button>
    </div>
  );
}

export default CuentasMoodle;