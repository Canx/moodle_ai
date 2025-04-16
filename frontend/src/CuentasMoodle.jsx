import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

function CuentasMoodle() {
  const { usuarioId } = useParams();
  const [cuentas, setCuentas] = useState([]);
  const [moodleUrl, setMoodleUrl] = useState("");
  const [usuarioMoodle, setUsuarioMoodle] = useState("");
  const [contrasenaMoodle, setContrasenaMoodle] = useState("");
  const [editId, setEditId] = useState(null);
  const [cursos, setCursos] = useState([]);
  const [cuentaSeleccionada, setCuentaSeleccionada] = useState(null);
  const [tareas, setTareas] = useState([]);
  const [cursoSeleccionado, setCursoSeleccionado] = useState(null);

  const obtenerCuentas = async () => {
    const response = await fetch(`/api/usuarios/${usuarioId}/cuentas`);
    const data = await response.json();
    setCuentas(data);
  };

  const limpiarFormulario = () => {
    setMoodleUrl("");
    setUsuarioMoodle("");
    setContrasenaMoodle("");
    setEditId(null);
  };

  const agregarOEditarCuenta = async () => {
    if (editId) {
      const response = await fetch(`/api/usuarios/${usuarioId}/cuentas/${editId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          moodle_url: moodleUrl,
          usuario_moodle: usuarioMoodle,
          contrasena_moodle: contrasenaMoodle,
        }),
      });
      if (response.ok) {
        obtenerCuentas();
        limpiarFormulario();
      }
    } else {
      const response = await fetch(`/api/usuarios/${usuarioId}/cuentas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          moodle_url: moodleUrl,
          usuario_moodle: usuarioMoodle,
          contrasena_moodle: contrasenaMoodle,
        }),
      });
      if (response.ok) {
        obtenerCuentas();
        limpiarFormulario();
      }
    }
  };

  const borrarCuenta = async (id) => {
    const response = await fetch(`/api/usuarios/${usuarioId}/cuentas/${id}`, {
      method: "DELETE",
    });
    if (response.ok) {
      obtenerCuentas();
    }
  };

  const editarCuenta = (cuenta) => {
    setEditId(cuenta.id);
    setMoodleUrl(cuenta.moodle_url);
    setUsuarioMoodle(cuenta.usuario_moodle);
    setContrasenaMoodle("");
  };

  const verCursos = async (cuentaId) => {
    setCuentaSeleccionada(cuentaId);
    const response = await fetch(`/api/cuentas/${cuentaId}/cursos`);
    if (response.ok) {
      const data = await response.json();
      setCursos(data);
    } else {
      setCursos([]);
    }
  };

  const verTareas = async (cursoId) => {
    setCursoSeleccionado(cursoId);
    const response = await fetch(`/api/cursos/${cursoId}/tareas`);
    if (response.ok) {
      const data = await response.json();
      setTareas(data);
    } else {
      setTareas([]);
    }
  };

  useEffect(() => {
    obtenerCuentas();
  }, []);

  return (
    <div>
      <h2>Mis Cuentas de Moodle</h2>
      <ul>
        {cuentas.map((cuenta) => (
          <li key={cuenta.id}>
            {cuenta.moodle_url} - {cuenta.usuario_moodle}
            <button onClick={() => editarCuenta(cuenta)} style={{ marginLeft: "10px" }}>
              Editar
            </button>
            <button onClick={() => borrarCuenta(cuenta.id)} style={{ marginLeft: "5px", color: "red" }}>
              Borrar
            </button>
            <button onClick={() => verCursos(cuenta.id)} style={{ marginLeft: "5px" }}>
              Ver
            </button>
            {cuentaSeleccionada === cuenta.id && (
              <div style={{ marginTop: "10px" }}>
                <strong>
                  Cursos sincronizados:
                  <button
                    style={{ marginLeft: "10px" }}
                    onClick={async () => {
                      // Llama al endpoint de sincronización
                      await fetch(`/api/cuentas/${cuenta.id}/sincronizar`, { method: "POST" });
                      // Vuelve a cargar los cursos sincronizados
                      verCursos(cuenta.id);
                    }}
                  >
                    Sincronizar
                  </button>
                </strong>
                <ul>
                  {cursos.length === 0 && <li>No hay cursos sincronizados.</li>}
                  {cursos.map((curso) => (
                    <li key={curso.id || curso.nombre}>{curso.nombre}</li>
                  ))}
                </ul>
              </div>
            )}
          </li>
        ))}
      </ul>
      <h3>{editId ? "Editar Cuenta" : "Agregar Cuenta"}</h3>
      <input
        type="text"
        placeholder="URL de Moodle"
        value={moodleUrl}
        onChange={(e) => setMoodleUrl(e.target.value)}
      />
      <input
        type="text"
        placeholder="Usuario de Moodle"
        value={usuarioMoodle}
        onChange={(e) => setUsuarioMoodle(e.target.value)}
      />
      <input
        type="password"
        placeholder="Contraseña de Moodle"
        value={contrasenaMoodle}
        onChange={(e) => setContrasenaMoodle(e.target.value)}
      />
      <button onClick={agregarOEditarCuenta}>
        {editId ? "Guardar Cambios" : "Agregar Cuenta"}
      </button>
      {editId && (
        <button onClick={limpiarFormulario} style={{ marginLeft: "10px" }}>
          Cancelar
        </button>
      )}
    </div>
  );
}

export default CuentasMoodle;