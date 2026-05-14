CREATE SCHEMA IF NOT EXISTS users_schema;
CREATE SCHEMA IF NOT EXISTS security_schema;
CREATE SCHEMA IF NOT EXISTS reservations_schema;
CREATE SCHEMA IF NOT EXISTS payments_schema;
CREATE SCHEMA IF NOT EXISTS notifications_schema;
CREATE SCHEMA IF NOT EXISTS properties_schema;
CREATE SCHEMA IF NOT EXISTS search_schema;

-- Accent-insensitive matching for properties.location filtering by city.
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Futuros microservicios:
CREATE SCHEMA IF NOT EXISTS inventory_schema;
-- CREATE SCHEMA IF NOT EXISTS currency_schema;
