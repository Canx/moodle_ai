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
    <div>
      <h2>Registro de Usuario</h2>
      {mensaje && <p className="text-green-500">{mensaje}</p>}
      <input
        type="text"
        placeholder="Nombre"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
      />
      <input
        type="email"
        placeholder="Correo"
        value={correo}
        onChange={(e) => setCorreo(e.target.value)}
      />
      <input
        type="password"
        placeholder="Contraseña"
        value={contrasena}
        onChange={(e) => setContrasena(e.target.value)}
      />
      <button onClick={registrarUsuario}>Registrar</button>
    </div>
  );
}

export default RegistroUsuario;