# 🎬 MyCima — AI-Powered Distributed Cinema Reservation Platform

**Intelligent Cinema. Connected Services.**

MyCima is an AI-powered cinema reservation platform built using a distributed microservices architecture. It allows users to discover movies, explore showtimes, select cinema seats, and make reservations through either a traditional booking interface or an intelligent AI assistant.

The project explores distributed systems concepts such as microservices, inter-service communication, asynchronous messaging, concurrency control, fault tolerance, and independent service deployment.

---

## 🎯 Project Objectives

The main objectives of MyCima are:

- Build a distributed application using independent microservices.
- Provide an intuitive cinema reservation experience.
- Integrate an AI assistant for intelligent movie recommendations and seat suggestions.
- Prevent double-booking through atomic seat reservation mechanisms.
- Implement asynchronous communication between services.
- Handle service failures and ensure system reliability.
- Evaluate system performance through functional, integration, and concurrency testing.

## ✨ Planned Features

- 🎥 **Movie Discovery:** Browse movies, genres, descriptions, and showtimes.
- 💺 **Interactive Seat Selection:** Visualize cinema halls and select available seats.
- 🤖 **AI Cinema Assistant:** Get movie recommendations and book seats using natural language.
- 🔐 **Authentication:** User registration, login, and JWT-based authentication.
- ⏳ **Temporary Seat Locking:** Hold selected seats for five minutes before confirmation.
- 💳 **Payment Simulation:** Simulate successful and failed payment transactions.
- 🔔 **Notifications:** Receive booking confirmations and reservation updates.
- ⚡ **Distributed Architecture:** Independent services communicating through modern protocols.

## 🏗️ System Architecture

MyCima follows a microservices architecture where each service has a specific responsibility and communicates with other services through network-based communication.

### Main Components

| Component | Responsibility |
|---|---|
| Frontend | User interface, seat map, booking and chatbot |
| API Gateway | Central entry point and request routing |
| User Service | Authentication and user management |
| Movie Service | Movies, cinemas, halls and showtimes |
| Reservation Service | Seat availability, locking and bookings |
| Payment Service | Simulated payment processing |
| Notification Service | Asynchronous booking notifications |
| AI Assistant Service | Intelligent recommendations and booking assistance |
| RabbitMQ | Asynchronous event communication |
| PostgreSQL | Persistent data storage |

### Communication Technologies

- **REST API:** HTTP-based communication using JSON.
- **gRPC:** Efficient internal service-to-service communication.
- **RabbitMQ:** Asynchronous messaging and event-driven communication.

## 🛠️ Technology Stack

| Category | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Messaging | RabbitMQ |
| Internal Communication | gRPC |
| Authentication | JWT |
| AI Integration | External LLM API with tool calling |
| Containerization | Docker, Docker Compose |
| Testing | Pytest, Locust |
| Version Control | Git, GitHub |

## 📁 Planned Project Structure

```text
mycima/
│
├── frontend/
├── gateway/
├── user-service/
├── movie-service/
├── reservation-service/
├── payment-service/
├── notification-service/
├── ai-assistant-service/
│
├── proto/
├── db/
│   ├── init.sql
│   └── seed/
│
├── tests/
├── docs/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## 🚀 Getting Started

The project is currently in its initial setup and architecture phase.

Development and deployment instructions will be added as the services are implemented.

### Prerequisites

The following tools are planned for development:

- Git and GitHub
- Docker Desktop
- Python 3.11+
- Node.js (LTS)
- Visual Studio Code
- PostgreSQL (Docker container)
- RabbitMQ (Docker container)

### Planned Deployment

Once the initial implementation is complete, the application will be launched using:

```bash
docker compose up --build
```

## 🧪 Testing and Evaluation

The project will include:

- Functional testing of individual services.
- Integration testing across microservices.
- Concurrent seat reservation testing.
- Performance and load testing using Locust.
- Failure simulation and fault-tolerance evaluation.

A key experiment will involve sending 100 simultaneous reservation requests for the same seat across two Reservation Service replicas, verifying that exactly one request succeeds.

## 👥 Contributors

MyCima is built collaboratively by:

- [@Robot404a](https://github.com/Robot404a)
- [@Abdelaali-dev-06](https://github.com/Abdelaali-dev-06)
- [@Youssefboulahnya](https://github.com/Youssefboulahnya)

---

**MyCima — Bringing intelligent cinema experiences to life.**
