import React, { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

function CuentaForm() {
  const { usuarioId, cuentaId } = useParams();
  const navigate = useNavigate();
  const isEdit = cuentaId && cuentaId !== "new";
  const [moodleUrl, setMoodleUrl] = useState("");
  const [usuarioMoodle, setUsuarioMoodle] = useState("");
  const [contrasenaMoodle, setContrasenaMoodle] = useState("");

  useEffect(() => {
    if (isEdit) {
      fetch(`/api/usuarios/${usuarioId}/cuentas/${cuentaId}`)
        .then((res) => res.json())
        .then((data) => {
          setMoodleUrl(data.moodle_url);
          setUsuarioMoodle(data.usuario_moodle);
        });
    }
  }, [isEdit, usuarioId, cuentaId]);

  const handleSubmit = async () => {
    const url = isEdit
      ? `/api/usuarios/${usuarioId}/cuentas/${cuentaId}`
      : `/api/usuarios/${usuarioId}/cuentas`;
    const method = isEdit ? "PUT" : "POST";
    await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        moodle_url: moodleUrl,
        usuario_moodle: usuarioMoodle,
        contrasena_moodle: contrasenaMoodle,
      }),
    });
    navigate(`/usuario/${usuarioId}/cuentas`);
  };

  const handleCancel = () => {
    navigate(`/usuario/${usuarioId}/cuentas`);
  };

  return (
    <div style={{ width: "95%", margin: "40px auto", background: "#fff", borderRadius: 18, boxShadow: "0 4px 24px #0002", padding: "36px 30px 40px 30px", textAlign: "center" }}>
      <h2 style={{ color: "#1976d2", fontSize: "2rem", marginBottom: 18 }}>
        {isEdit ? "Editar Cuenta" : "Agregar Cuenta"}
      </h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 480, margin: "0 auto" }}>
        <input
          type="text"
          placeholder="URL de Moodle"
          value={moodleUrl}
          onChange={(e) => setMoodleUrl(e.target.value)}
          style={{ width: "100%", padding: "12px 14px", borderRadius: 7, border: "1px solid #b9c6e0", fontSize: "1rem", outline: "none" }}
        />
        <input
          type="text"
          placeholder="Usuario de Moodle"
          value={usuarioMoodle}
          onChange={(e) => setUsuarioMoodle(e.target.value)}
          style={{ width: "100%", padding: "12px 14px", borderRadius: 7, border: "1px solid #b9c6e0", fontSize: "1rem", outline: "none" }}
        />
        <input
          type="password"
          placeholder="Contraseña de Moodle"
          value={contrasenaMoodle}
          onChange={(e) => setContrasenaMoodle(e.target.value)}
          style={{ width: "100%", padding: "12px 14px", borderRadius: 7, border: "1px solid #b9c6e0", fontSize: "1rem", outline: "none" }}
        />
        <div style={{ display: "flex", justifyContent: "center", gap: 12 }}>
          <button
            onClick={handleSubmit}
            style={{ background: "#1976d2", color: "#fff", border: "none", borderRadius: 7, padding: "12px 24px", fontWeight: 600, fontSize: "1rem", cursor: "pointer", boxShadow: "0 2px 8px #0001", transition: "background 0.2s" }}
            onMouseOver={(e) => (e.currentTarget.style.background = "#125fa2")}
            onMouseOut={(e) => (e.currentTarget.style.background = "#1976d2")}
          >
            {isEdit ? "Guardar Cambios" : "Agregar Cuenta"}
          </button>
          <button
            onClick={handleCancel}
            style={{ background: "#e3eefd", color: "#1976d2", border: "none", borderRadius: 7, padding: "12px 24px", fontWeight: 600, fontSize: "1rem", cursor: "pointer", transition: "background 0.2s" }}
            onMouseOver={(e) => (e.currentTarget.style.background = "#d1e2fc")}
            onMouseOut={(e) => (e.currentTarget.style.background = "#e3eefd")}
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}

export default CuentaForm;
