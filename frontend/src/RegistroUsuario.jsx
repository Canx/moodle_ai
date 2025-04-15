import React, { useState } from "react";

function RegistroUsuario() {
  const [nombre, setNombre] = useState("");
  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");

  const registrarUsuario = async () => {
    const response = await fetch("/api/usuarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre, correo, contrasena }),
    });
    const data = await response.json();
    if (response.ok) {
      alert("Usuario registrado exitosamente");
    } else {
      alert(data.detail);
    }
  };

  return (
    <div>
      <h2>Registro de Usuario</h2>
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