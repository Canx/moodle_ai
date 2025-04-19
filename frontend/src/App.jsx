import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Route, Routes, Link, Navigate, useNavigate } from "react-router-dom";
import RegistroUsuario from "./RegistroUsuario";
import Usuario from "./Usuario";
import { Navbar, Nav, Container } from "react-bootstrap";
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

  return (
    <Router>
      <AppRoutes usuarioId={usuarioId} setUsuarioId={setUsuarioId} />
    </Router>
  );
}

function AppRoutes({ usuarioId, setUsuarioId }) {
  const navigate = useNavigate();
  const cerrarSesion = () => {
    localStorage.removeItem("usuarioId");
    setUsuarioId(null);
    navigate('/');
  };

  return (
    <>
      <Navbar bg="white" expand="md" className="border-bottom shadow-sm mb-0">
        <Container>
          <Navbar.Brand as={Link} to="/">
            <img src="/logo.svg" alt="Logo" width={36} height={36} className="me-2 align-middle" />
            <span className="align-middle fw-bold text-primary">Moodle AI Tasks</span>
          </Navbar.Brand>
          <Navbar.Toggle aria-controls="main-navbar-nav" />
          <Navbar.Collapse id="main-navbar-nav">
            <Nav className="ms-auto align-items-center gap-2">
              {usuarioId && <Nav.Link as={Link} to="/" className="fw-semibold">Inicio</Nav.Link>}
              {!usuarioId && <Nav.Link as={Link} to="/login" className="p-0"><button className="btn btn-outline-primary btn-sm ms-2">Login</button></Nav.Link>}
              {!usuarioId && <Nav.Link as={Link} to="/registro" className="p-0"><button className="btn btn-outline-primary btn-sm ms-2">Registro</button></Nav.Link>}
              {usuarioId && <Nav.Link as={Link} to={`/usuario/${usuarioId}`} className="fw-semibold">Mi Cuenta</Nav.Link>}
              {usuarioId && <Nav.Item as="span" className="ms-2"><button className="btn btn-outline-danger btn-sm" onClick={cerrarSesion}>Cerrar Sesión</button></Nav.Item>}
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>
      <div>
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
  );
}

export default App;