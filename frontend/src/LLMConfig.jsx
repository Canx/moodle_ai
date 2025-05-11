import React, { useState, useEffect } from 'react';

function LLMConfig({ usuarioId }) {
  const [configs, setConfigs] = useState([]);
  const [selectedConfig, setSelectedConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Cargar todas las configuraciones de LLM disponibles
    fetch('/api/llm_configs')
      .then(res => res.json())
      .then(data => {
        setConfigs(data);
        setLoading(false);
      })
      .catch(err => {
        setError('Error cargando configuraciones de LLM');
        setLoading(false);
      });

    // Obtener la configuración actual del usuario
    if (usuarioId) {
      fetch(`/api/usuarios/${usuarioId}/llm_config`)
        .then(res => res.json())
        .then(data => {
          setSelectedConfig(data);
        })
        .catch(err => {
          setError('Error cargando la configuración del usuario');
        });
    }
  }, [usuarioId]);

  const handleConfigChange = (configId) => {
    if (!usuarioId) return;

    fetch(`/api/usuarios/${usuarioId}/llm_config/${configId}/set_default`, {
      method: 'POST'
    })
      .then(res => {
        if (!res.ok) throw new Error('Error actualizando la configuración');
        return res.json();
      })
      .then(() => {
        // Actualizar la configuración seleccionada
        const newConfig = configs.find(c => c.id === configId);
        setSelectedConfig(newConfig);
      })
      .catch(err => {
        setError('Error guardando la configuración');
      });
  };

  if (loading) return <div>Cargando configuraciones...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="llm-config" style={{padding: '20px'}}>
      <h2>Configuración de LLM</h2>
      <p>Selecciona el LLM que quieres usar por defecto para las evaluaciones:</p>
      
      <div className="llm-options" style={{display: 'grid', gap: '10px', maxWidth: '600px', margin: '20px 0'}}>
        {configs.map(config => (
          <div 
            key={config.id} 
            className={`llm-option ${selectedConfig?.id === config.id ? 'selected' : ''}`}
            style={{
              padding: '15px',
              border: '1px solid #ccc',
              borderRadius: '8px',
              cursor: 'pointer',
              backgroundColor: selectedConfig?.id === config.id ? '#e3f2fd' : '#fff',
            }}
            onClick={() => handleConfigChange(config.id)}
          >
            <div style={{fontWeight: 'bold'}}>{config.nombre}</div>
            {config.descripcion && <div style={{color: '#666', fontSize: '0.9em'}}>{config.descripcion}</div>}
            {selectedConfig?.id === config.id && (
              <div style={{color: '#2196f3', fontSize: '0.9em', marginTop: '5px'}}>
                ✓ Seleccionado
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default LLMConfig;
