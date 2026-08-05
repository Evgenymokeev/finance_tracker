# Finance Tracker API

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6.0-green)
![DRF](https://img.shields.io/badge/Django_REST_Framework-3.17-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![Coverage](https://img.shields.io/badge/Coverage-96%25-brightgreen)

REST API application for personal finance management.

The project allows users to manage expenses, categories, export data and analyze spending statistics.

Built as a backend portfolio project using modern Python technologies.

---

# 🚀 Features

## Authentication

- User registration
- JWT authentication
- Access and refresh tokens
- Protected API endpoints
- User profile management
- Password change functionality


## Expenses

- Create expenses
- Update expenses
- Delete expenses
- User-specific expense management
- Expense filtering
- Searching
- Sorting
- CSV export


## Categories

- Personal categories for each user
- Default categories created automatically
- Category validation


## Analytics

- Total expenses dashboard
- Monthly expenses statistics
- Expenses grouped by category


## Background tasks

- Celery integration
- Redis message broker
- Asynchronous expense notifications


---

# 🛠 Tech Stack

## Backend

- Python 3.12
- Django 6
- Django REST Framework


## Database

- PostgreSQL 17


## Authentication

- JWT
- Simple JWT


## Documentation

- Swagger / OpenAPI
- drf-spectacular


## Async Processing

- Celery
- Redis


## DevOps

- Docker
- Docker Compose
- GitHub Actions CI


## Testing

- Pytest
- Pytest Coverage
- Test Coverage: 96%


---

# 📦 Installation

## Clone repository

```bash
git clone https://github.com/Evgenymokeev/finance_tracker.git

cd finance_tracker

