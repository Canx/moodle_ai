-- Modificar tabla sincronizaciones para ser por curso en lugar de por cuenta
ALTER TABLE sincronizaciones DROP CONSTRAINT sincronizaciones_cuenta_id_fkey;
ALTER TABLE sincronizaciones ADD COLUMN curso_id INTEGER;
ALTER TABLE sincronizaciones DROP CONSTRAINT sincronizaciones_pkey;
ALTER TABLE sincronizaciones ADD PRIMARY KEY (cuenta_id, curso_id);
ALTER TABLE sincronizaciones ADD CONSTRAINT sincronizaciones_cuenta_id_fkey FOREIGN KEY (cuenta_id) REFERENCES cuentas_moodle(id) ON DELETE CASCADE;
ALTER TABLE sincronizaciones ADD CONSTRAINT sincronizaciones_curso_id_fkey FOREIGN KEY (curso_id) REFERENCES cursos(id) ON DELETE CASCADE;
