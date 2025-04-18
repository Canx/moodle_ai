import React from "react";
import { Link } from "react-router-dom";

export default function Inicio() {
  return (
    <div style={{minHeight: 'calc(100vh - 64px)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'transparent'}}>
      <div style={{width: '95%', margin: '0 auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '48px 36px', textAlign: 'center'}}>
        <img src="/logo.svg" alt="Logo" style={{width: 90, height: 90, marginBottom: 24, opacity: 0.9, display: 'inline-block'}} />
        <h1 style={{color: '#1976d2', fontSize: '2.5rem', marginBottom: 18}}>Bienvenido a Moodle AI Tasks</h1>
        <p style={{color: '#444', fontSize: '1.18rem', marginBottom: 38}}>
          Gestiona y sincroniza tus tareas de Moodle de forma sencilla y visual.<br/>
          Accede con tu cuenta para comenzar.
        </p>
        <Link to="/login" style={{background: '#1976d2', color: '#fff', padding: '14px 38px', borderRadius: 8, fontWeight: 600, fontSize: '1.15rem', textDecoration: 'none', boxShadow: '0 2px 12px #1976d233'}}>Iniciar Sesión</Link>
        <div style={{marginTop: 22}}>
          <span style={{color:'#888', fontSize:'1rem'}}>¿No tienes cuenta?</span>
          <Link to="/registro" style={{marginLeft: 8, color: '#1976d2', fontWeight: 500, textDecoration: 'underline'}}>Registrarse</Link>
        </div>
      </div>
    </div>
  );
}
