import React from "react";
import { Link } from "react-router-dom";
import { Navbar, Nav, Container } from "react-bootstrap";

export default function Inicio() {
  return (
    <>
      
      <div className="w-100 min-vh-100 d-flex align-items-center justify-content-center bg-light">
        <div className="container">
          <div className="row justify-content-center">
            <div className="col-12 col-md-8 col-lg-6">
              <div className="card shadow-lg p-4 p-md-5 w-100 mx-auto">
                <div className="text-center mb-4">
                  <img src="/logo.svg" alt="Logo" className="mb-3" width={90} height={90} style={{ opacity: 0.9 }} />
                </div>
                <h1 className="mb-3 fw-bold text-primary text-center fs-2">
                  Bienvenido a Moodle AI Tasks
                </h1>
                <p className="mb-4 text-secondary text-center fs-5">
                  Gestiona y sincroniza tus tareas de Moodle de forma sencilla y visual.<br />
                  Accede con tu cuenta para comenzar.
                </p>
                <div className="d-grid gap-2 mb-3">
                  <Link to="/login" className="btn btn-primary btn-lg fw-semibold shadow-sm">
                    Iniciar Sesión
                  </Link>
                </div>
                <div className="text-center mt-3">
                  <span className="text-muted">¿No tienes cuenta?</span>
                  <Link to="/registro" className="ms-2 fw-semibold text-decoration-underline text-primary">
                    Registrarse
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

