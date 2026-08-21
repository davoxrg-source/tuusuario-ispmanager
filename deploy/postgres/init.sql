-- Ejecutar como el usuario postgres: sudo -u postgres psql -f deploy/postgres/init.sql
CREATE ROLE ispmanager WITH LOGIN PASSWORD 'changeme';
CREATE DATABASE ispmanager OWNER ispmanager;
CREATE DATABASE ispmanager_test OWNER ispmanager;
