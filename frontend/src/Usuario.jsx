import React from "react";
import { Link, useParams } from "react-router-dom";

function Usuario() {
  const { usuarioId } = useParams();

  return (
    <div style={{width: '95%', margin: '60px auto', background: '#fff', borderRadius: 18, boxShadow: '0 4px 24px #0002', padding: '48px 36px', textAlign: 'center'}}>
      <h2 style={{color: '#1976d2', fontSize: '2rem', marginBottom: 18}}>Bienvenido, Usuario {usuarioId}</h2>
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