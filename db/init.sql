-- First-start initialisation for the shared PostgreSQL container.
-- Each service owns exactly one database and one role: append your own block
-- when you add a service. This file only runs when the `pgdata` volume is empty.
--
-- The passwords below are development-only. They are also the defaults used by
-- docker-compose.yml; override both sides together for anything beyond a demo.

CREATE ROLE user_svc LOGIN PASSWORD 'user_svc_pass';

CREATE DATABASE users_db OWNER user_svc;
