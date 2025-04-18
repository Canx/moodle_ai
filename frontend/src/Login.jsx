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

  const [mostrarContrasena, setMostrarContrasena] = useState(false);

  return (
    <div style={{width: '100vw', minHeight: '100vh', background: 'linear-gradient(135deg, #e3eefd 0%, #f7fafd 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{width: 420, maxWidth: '95vw', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '48px 36px 36px 36px', textAlign: 'center', margin: '30px 0'}}>
        <div style={{marginBottom: 18}}>
          {/* SVG de libro abierto con check */}
          <svg width="56" height="56" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg" style={{marginBottom: 8}}>
            <rect width="56" height="56" rx="16" fill="#e3eefd"/>
            <path d="M16 38V20.5C16 18.0147 18.0147 16 20.5 16H35.5C37.9853 16 40 18.0147 40 20.5V38" stroke="#1976d2" strokeWidth="2.2" strokeLinejoin="round"/>
            <path d="M16 38C17.5 36.5 21.5 34 28 34C34.5 34 38.5 36.5 40 38" stroke="#1976d2" strokeWidth="2.2" strokeLinejoin="round"/>
            <path d="M23 26L27 30L34 23" stroke="#43a047" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="28" cy="28" r="26" stroke="#1976d2" strokeWidth="1.2"/>
          </svg>
        </div>
        <h2 style={{color: '#1976d2', fontSize: '2.1rem', marginBottom: 20, fontWeight: 700}}>Iniciar Sesión</h2>
        {mensaje && <div style={{background: '#fdecea', color: '#d32f2f', borderRadius: 6, padding: '10px 0', marginBottom: 16, fontWeight: 500, fontSize: '1.07rem'}}>{mensaje}</div>}
        <input
          type="text"
          placeholder="Correo o Nombre de Usuario"
          value={identificador}
          onChange={(e) => setIdentificador(e.target.value)}
          style={{width: '100%', padding: '14px 14px', borderRadius: 7, border: '1.5px solid #b9c5d8', marginBottom: 16, fontSize: '1.08rem', outline: 'none', boxSizing: 'border-box'}}
          autoFocus
        />
        <div style={{position: 'relative', width: '100%', marginBottom: 18}}>
          <input
            type={mostrarContrasena ? 'text' : 'password'}
            placeholder="Contraseña"
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
            style={{width: '100%', padding: '14px 46px 14px 14px', borderRadius: 7, border: '1.5px solid #b9c5d8', fontSize: '1.08rem', outline: 'none', boxSizing: 'border-box'}}
          />
          <button
            type="button"
            onClick={() => setMostrarContrasena(m => !m)}
            style={{position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#1976d2', fontWeight: 600, cursor: 'pointer', fontSize: 15, padding: 0}}
            tabIndex={-1}
            aria-label={mostrarContrasena ? 'Ocultar contraseña' : 'Mostrar contraseña'}
          >
            {mostrarContrasena ? '🙈' : '👁️'}
          </button>
        </div>
        <button
          onClick={iniciarSesion}
          style={{width: '100%', background: '#1976d2', color: '#fff', border: 'none', borderRadius: 7, padding: '14px 0', fontWeight: 700, fontSize: '1.15rem', marginBottom: 18, boxShadow: '0 2px 8px #1976d225', cursor: 'pointer', transition: 'background 0.2s'}}
          onMouseOver={e => e.currentTarget.style.background='#1456a0'}
          onMouseOut={e => e.currentTarget.style.background='#1976d2'}
        >
          Iniciar Sesión
        </button>
        <div style={{marginTop: 8, fontSize: '1.01rem', color: '#444'}}>
          ¿No tienes cuenta?
          <a href="/registro" style={{color: '#1976d2', marginLeft: 6, textDecoration: 'underline', fontWeight: 600}}>Regístrate</a>
        </div>
      </div>
    </div>
  );
}

export default Login;