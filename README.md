# Finance Tracker API

REST API application for personal finance management.

The project allows users to manage expenses, categories, and analyze spending statistics.

Built as a backend portfolio project using modern Python technologies.

---

## 🚀 Features

### Authentication
- User registration
- JWT authentication
- Access and refresh tokens
- Protected API endpoints

### Expenses
- Create expenses
- Update expenses
- Delete expenses
- User-specific expense management
- Expense filtering and searching

### Categories
- Personal categories for each user
- Default categories created automatically
- Category validation

### Analytics
- Total expenses dashboard
- Monthly expenses statistics
- Expenses grouped by category

### Background tasks
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

## Async processing

- Celery
- Redis

## DevOps

- Docker
- Docker Compose
- GitHub Actions CI

---

# 📦 Installation

## Clone repository

```bash
git clone https://github.com/Evgenymokeev/finance_tracker.git

cd finance_tracker
