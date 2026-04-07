CREATE SCHEMA IF NOT EXISTS users_schema;
CREATE SCHEMA IF NOT EXISTS security_schema;
CREATE SCHEMA IF NOT EXISTS reservations_schema;
CREATE SCHEMA IF NOT EXISTS search_schema;

-- Search service tables
CREATE TABLE IF NOT EXISTS search_schema.propiedades (
	id UUID PRIMARY KEY,
	nombre VARCHAR(160) NOT NULL,
	ciudad VARCHAR(120) NOT NULL,
	pais VARCHAR(120) NOT NULL,
	direccion VARCHAR(250),
	descripcion TEXT,
	estado_activo BOOLEAN NOT NULL DEFAULT TRUE,
	capacidad_maxima INTEGER NOT NULL,
	imagen_principal_url VARCHAR(500),
	rating DOUBLE PRECISION,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_schema.amenidades (
	id UUID PRIMARY KEY,
	nombre VARCHAR(120) NOT NULL UNIQUE,
	categoria VARCHAR(120)
);

CREATE TABLE IF NOT EXISTS search_schema.tipos_habitacion (
	id UUID PRIMARY KEY,
	propiedad_id UUID NOT NULL REFERENCES search_schema.propiedades(id),
	nombre VARCHAR(140) NOT NULL,
	descripcion TEXT,
	capacidad INTEGER NOT NULL,
	estado_activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS search_schema.planes_tarifa (
	id UUID PRIMARY KEY,
	tipo_habitacion_id UUID NOT NULL REFERENCES search_schema.tipos_habitacion(id),
	nombre VARCHAR(140) NOT NULL,
	descripcion TEXT,
	moneda VARCHAR(3) NOT NULL DEFAULT 'USD',
	precio_base NUMERIC(12, 2) NOT NULL DEFAULT 0,
	estado_activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS search_schema.calendario_inventario (
	id UUID PRIMARY KEY,
	tipo_habitacion_id UUID NOT NULL REFERENCES search_schema.tipos_habitacion(id),
	fecha DATE NOT NULL,
	unidades_disponibles INTEGER NOT NULL DEFAULT 0,
	unidades_bloqueadas INTEGER NOT NULL DEFAULT 0,
	CONSTRAINT uq_calendario_inventario_tipo_habitacion_fecha
		UNIQUE (tipo_habitacion_id, fecha)
);

CREATE TABLE IF NOT EXISTS search_schema.calendario_tarifas (
	id UUID PRIMARY KEY,
	plan_tarifa_id UUID NOT NULL REFERENCES search_schema.planes_tarifa(id),
	fecha DATE NOT NULL,
	precio NUMERIC(12, 2) NOT NULL DEFAULT 0,
	CONSTRAINT uq_calendario_tarifas_plan_tarifa_fecha
		UNIQUE (plan_tarifa_id, fecha)
);

CREATE TABLE IF NOT EXISTS search_schema.servicios (
	id UUID PRIMARY KEY,
	propiedad_id UUID NOT NULL REFERENCES search_schema.propiedades(id),
	nombre VARCHAR(120) NOT NULL,
	descripcion TEXT,
	estado_activo BOOLEAN NOT NULL DEFAULT TRUE,
	CONSTRAINT uq_servicios_propiedad_nombre
		UNIQUE (propiedad_id, nombre)
);

CREATE TABLE IF NOT EXISTS search_schema.propiedad_amenidad (
	propiedad_id UUID NOT NULL REFERENCES search_schema.propiedades(id),
	amenidad_id UUID NOT NULL REFERENCES search_schema.amenidades(id),
	PRIMARY KEY (propiedad_id, amenidad_id)
);

CREATE INDEX IF NOT EXISTS ix_propiedades_ciudad
	ON search_schema.propiedades (ciudad);
CREATE INDEX IF NOT EXISTS ix_propiedades_estado_activo
	ON search_schema.propiedades (estado_activo);
CREATE INDEX IF NOT EXISTS ix_propiedades_capacidad_maxima
	ON search_schema.propiedades (capacidad_maxima);
CREATE INDEX IF NOT EXISTS ix_propiedades_rating
	ON search_schema.propiedades (rating);

CREATE INDEX IF NOT EXISTS ix_tipos_habitacion_propiedad_id
	ON search_schema.tipos_habitacion (propiedad_id);
CREATE INDEX IF NOT EXISTS ix_tipos_habitacion_capacidad
	ON search_schema.tipos_habitacion (capacidad);
CREATE INDEX IF NOT EXISTS ix_tipos_habitacion_estado_activo
	ON search_schema.tipos_habitacion (estado_activo);

CREATE INDEX IF NOT EXISTS ix_planes_tarifa_tipo_habitacion_id
	ON search_schema.planes_tarifa (tipo_habitacion_id);
CREATE INDEX IF NOT EXISTS ix_planes_tarifa_estado_activo
	ON search_schema.planes_tarifa (estado_activo);

CREATE INDEX IF NOT EXISTS ix_calendario_inventario_tipo_habitacion_id
	ON search_schema.calendario_inventario (tipo_habitacion_id);
CREATE INDEX IF NOT EXISTS ix_calendario_inventario_fecha
	ON search_schema.calendario_inventario (fecha);

CREATE INDEX IF NOT EXISTS ix_calendario_tarifas_plan_tarifa_id
	ON search_schema.calendario_tarifas (plan_tarifa_id);
CREATE INDEX IF NOT EXISTS ix_calendario_tarifas_fecha
	ON search_schema.calendario_tarifas (fecha);

CREATE INDEX IF NOT EXISTS ix_servicios_propiedad_id
	ON search_schema.servicios (propiedad_id);
CREATE INDEX IF NOT EXISTS ix_propiedad_amenidad_amenidad_id
	ON search_schema.propiedad_amenidad (amenidad_id);

-- Futuros microservicios:
-- CREATE SCHEMA IF NOT EXISTS properties_schema;
-- CREATE SCHEMA IF NOT EXISTS payments_schema;
-- CREATE SCHEMA IF NOT EXISTS inventory_schema;
-- CREATE SCHEMA IF NOT EXISTS currency_schema;
