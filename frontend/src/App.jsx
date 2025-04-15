import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Route, Routes, Link } from "react-router-dom";
import RegistroUsuario from "./RegistroUsuario";
import Usuario from "./Usuario";
import CuentasMoodle from "./CuentasMoodle";
import Login from "./Login";

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
      <div>
        <nav>
          <Link to="/">Inicio</Link>
          {!usuarioId && <Link to="/registro">Registro</Link>}
          {usuarioId && (
            <>
              <Link to={`/usuario/${usuarioId}`}>Mi Cuenta</Link>
              <button onClick={cerrarSesion} style={{ marginLeft: "10px" }}>
                Cerrar Sesión
              </button>
            </>
          )}
        </nav>
        <Routes>
          <Route
            path="/"
            element={<Login setUsuarioId={(id) => {
              setUsuarioId(id);
              localStorage.setItem("usuarioId", id); // Guardar en localStorage
            }} />}
          />
          <Route path="/registro" element={<RegistroUsuario setUsuarioId={setUsuarioId} />} />
          <Route path="/usuario/:usuarioId" element={<Usuario />} />
          <Route path="/usuario/:usuarioId/cuentas" element={<CuentasMoodle />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;