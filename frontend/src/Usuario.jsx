import React from "react";
import { Link, useParams } from "react-router-dom";

function Usuario() {
  const { usuarioId } = useParams();

  return (
    <div>
      <h2>Bienvenido, Usuario {usuarioId}</h2>
      <nav>
        <ul>
          <li>
            <Link to={`/usuario/${usuarioId}/cuentas`}>Gestionar Cuentas de Moodle</Link>
          </li>
          <li>
            <Link to="/">Volver al Inicio</Link>
          </li>
        </ul>
      </nav>
    </div>
  );
}

export default Usuario;