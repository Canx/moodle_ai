import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

function Login({ setUsuarioId }) {
  const [identificador, setIdentificador] = useState(""); // Puede ser correo o nombre de usuario
  const [contrasena, setContrasena] = useState("");
  const [mensaje, setMensaje] = useState("");
  const navigate = useNavigate();

  const iniciarSesion = async () => {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identificador, contrasena }),
    });
    const data = await response.json();

    if (response.ok) {
      setUsuarioId(data.usuarioId); // Actualiza el estado global
      localStorage.setItem("usuarioId", data.usuarioId); // Guarda en localStorage
      navigate(`/usuario/${data.usuarioId}`);
    } else {
      setMensaje(data.detail || "Error al iniciar sesión");
    }
  };

  return (
    <div style={{width: '95%', margin: '60px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '48px 36px', textAlign: 'center'}}>
      <h2 style={{color: '#1976d2', fontSize: '2rem', marginBottom: 18}}>Iniciar Sesión</h2>
      {mensaje && <p className="text-red-500">{mensaje}</p>}
      <input
        type="text"
        placeholder="Correo o Nombre de Usuario"
        value={identificador}
        onChange={(e) => setIdentificador(e.target.value)}
      />
      <input
        type="password"
        placeholder="Contraseña"
        value={contrasena}
        onChange={(e) => setContrasena(e.target.value)}
      />
      <button onClick={iniciarSesion}>Iniciar Sesión</button>
    </div>
  );
}

export default Login;