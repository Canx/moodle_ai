import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Route, Routes, Link, Navigate } from "react-router-dom";
import RegistroUsuario from "./RegistroUsuario";
import Usuario from "./Usuario";
import CuentasMoodle from "./CuentasMoodle";
import CursosDeCuenta from "./CursosDeCuenta";
import TareasDeCurso from "./TareasDeCurso";
import TareaIndividual from "./TareaIndividual";
import Login from "./Login";
import Inicio from "./Inicio";

function App() {
  const [usuarioId, setUsuarioId] = useState(null);

  // Cargar el estado de la sesión desde localStorage al iniciar la aplicación
  useEffect(() => {
    const storedUsuarioId = localStorage.getItem("usuarioId");
    if (storedUsuarioId) {
      setUsuarioId(storedUsuarioId);
    }
  }, []);

  // Manejar el cierre de sesión
  const cerrarSesion = () => {
    localStorage.removeItem("usuarioId");
    setUsuarioId(null);
  };

  return (
    <Router>
      <>
        <header style={{position: 'fixed', top: 0, left: 0, width: '100%', background: '#fff', boxShadow: '0 2px 12px #0001', zIndex: 1000, padding: '0 0', borderBottom: '1px solid #e5e5e5'}}>
          <nav style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 36px', maxWidth: 1200, margin: '0 auto'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
              <Link to="/" style={{display: 'flex', alignItems: 'center', marginRight: 18, textDecoration: 'none'}} aria-label="Inicio">
                <img src="/logo.svg" alt="Logo" style={{width: 38, height: 38, display: 'block'}} />
              </Link>
            </div>
            <div style={{display: 'flex', alignItems: 'center', gap: 28}}>
              <Link to="/" style={{color: '#1976d2', textDecoration: 'none', fontWeight: 600, fontSize: '1.13rem', letterSpacing: '.01em'}}>Inicio</Link>
              {!usuarioId && (
                <Link to="/registro" style={{color: '#1976d2', textDecoration: 'none', fontWeight: 600, fontSize: '1.13rem'}}>Registro</Link>
              )}
              {usuarioId && (
                <>
                  <Link to={`/usuario/${usuarioId}`} style={{color: '#1976d2', textDecoration: 'none', fontWeight: 600, fontSize: '1.13rem'}}>Mi Cuenta</Link>
                  <button onClick={cerrarSesion} style={{ marginLeft: 18, background: '#e3eefd', color: '#1976d2', border: 'none', borderRadius: 6, padding: '8px 18px', fontWeight: 600, fontSize: '1.05rem', cursor: 'pointer', transition: 'background 0.2s' }}
                    onMouseOver={e => e.currentTarget.style.background='#d1e2fc'}
                    onMouseOut={e => e.currentTarget.style.background='#e3eefd'}>
                    Cerrar Sesión
                  </button>
                </>
              )}
            </div>
          </nav>
        </header>
        <div style={{paddingTop: 64}}>
          <Routes>
            <Route path="/" element={<Inicio />} />
            <Route
              path="/login"
              element={<Login setUsuarioId={(id) => {
                setUsuarioId(id);
                localStorage.setItem("usuarioId", id); // Guardar en localStorage
              }} />}
            />
            <Route path="/registro" element={<RegistroUsuario setUsuarioId={setUsuarioId} />} />
            <Route path="/usuario/:usuarioId" element={<Usuario />} />
            <Route
              path="/usuario/:usuarioId/cuentas"
              element={
                usuarioId ? (
                  <CuentasMoodle />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />
            <Route path="/usuario/:usuarioId/cuentas/:cuentaId/cursos" element={<CursosDeCuenta />} />
            <Route path="/usuario/:usuarioId/cuentas/:cuentaId/cursos/:cursoId/tareas" element={<TareasDeCurso />} />
            <Route path="/usuario/:usuarioId/cuentas/:cuentaId/cursos/:cursoId/tareas/:tareaId/detalle" element={<TareaIndividual />} />
          </Routes>
        </div>
      </>
    </Router>
  );
}

export default App;