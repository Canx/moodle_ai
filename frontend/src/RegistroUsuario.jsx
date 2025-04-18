import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

function RegistroUsuario({ setUsuarioId }) {
  const [nombre, setNombre] = useState("");
  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [mensaje, setMensaje] = useState(""); // Estado para mostrar mensajes
  const navigate = useNavigate();

  const registrarUsuario = async () => {
    const response = await fetch("/api/usuarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre, correo, contrasena }),
    });
    const data = await response.json();

    if (response.ok) {
      setMensaje("Usuario registrado correctamente");
      setUsuarioId(data.id); // Guarda el ID del usuario registrado
      navigate(`/usuario/${data.id}`); // Redirige a la página del usuario
    } else {
      setMensaje(data.detail || "Error al registrar el usuario");
    }
  };

  return (
    <div style={{width: '95%', maxWidth: 420, margin: '60px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '48px 36px', textAlign: 'center'}}>
      <h2 style={{color: '#1976d2', fontSize: '2rem', marginBottom: 24}}>Registro de Usuario</h2>
      {mensaje && <p style={{color: '#388e3c', marginBottom: 24, fontWeight: 500}}>{mensaje}</p>}
      <div style={{display: 'flex', flexDirection: 'column', gap: 18, marginBottom: 18}}>
        <input
          type="text"
          placeholder="Nombre"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          style={{padding: '12px 16px', borderRadius: 8, border: '1px solid #dbeafe', fontSize: 16, background: '#f6f8fa'}}
        />
        <input
          type="email"
          placeholder="Correo"
          value={correo}
          onChange={(e) => setCorreo(e.target.value)}
          style={{padding: '12px 16px', borderRadius: 8, border: '1px solid #dbeafe', fontSize: 16, background: '#f6f8fa'}}
        />
        <input
          type="password"
          placeholder="Contraseña"
          value={contrasena}
          onChange={(e) => setContrasena(e.target.value)}
          style={{padding: '12px 16px', borderRadius: 8, border: '1px solid #dbeafe', fontSize: 16, background: '#f6f8fa'}}
        />
      </div>
      <button
        onClick={registrarUsuario}
        style={{
          backgroundColor: '#1976d2',
          color: '#fff',
          padding: '12px 24px',
          border: 'none',
          borderRadius: 8,
          fontWeight: 600,
          fontSize: 17,
          cursor: 'pointer',
          boxShadow: '0 2px 8px #0001',
          transition: 'background 0.2s',
          marginTop: 8
        }}
        onMouseOver={e => e.currentTarget.style.backgroundColor = '#125fa2'}
        onMouseOut={e => e.currentTarget.style.backgroundColor = '#1976d2'}
      >
        Registrar
      </button>
    </div>
  );
}

export default RegistroUsuario;