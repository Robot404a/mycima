-- First-start initialisation for the shared PostgreSQL container.
-- Each service owns exactly one database and one role: append your own block
-- when you add a service. This file only runs when the `pgdata` volume is empty.
--
-- The passwords below are development-only. They are also the defaults used by
-- docker-compose.yml; override both sides together for anything beyond a demo.

CREATE ROLE user_svc LOGIN PASSWORD 'user_svc_pass';

CREATE DATABASE users_db OWNER user_svc;

-- Movie service: catalog (movies, cinemas, halls, showtimes)
CREATE ROLE movie_svc LOGIN PASSWORD 'movie_svc_pass';
CREATE DATABASE movies_db OWNER movie_svc;

-- Reservation service: holds, seat claims, bookings
CREATE ROLE reservation_svc LOGIN PASSWORD 'reservation_svc_pass';
CREATE DATABASE reservation_db OWNER reservation_svc;

-- AI assistant service: conversations and seat proposals
CREATE ROLE ai_svc LOGIN PASSWORD 'ai_svc_pass';
CREATE DATABASE ai_assistant_db OWNER ai_svc;

-- Payment service: simulated transactions, one row per reservation hold
CREATE ROLE payment_svc LOGIN PASSWORD 'payment_svc_pass';
CREATE DATABASE payment_db OWNER payment_svc;
