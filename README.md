# Finance Tracker API

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6.0-green)
![DRF](https://img.shields.io/badge/Django_REST_Framework-3.17-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![Coverage](https://img.shields.io/badge/Coverage-96%25-brightgreen)

REST API application for personal finance management.

The project allows users to manage expenses, categories, budgets, financial goals, currencies and analyze spending statistics.

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
- Password reset functionality

## Expenses

- Create expenses
- Update expenses
- Delete expenses
- User-specific expense management
- Expense filtering
- Searching
- Sorting
- CSV export
- Excel export
- Multi-currency expense support

## Categories

- Personal categories for each user
- Default categories created automatically
- Category validation

## Budgets

- Create and manage budgets
- Category-based budgets
- Monthly budget tracking
- Multi-currency budget support
- Budget progress tracking

## Financial Goals

- Create and manage financial goals
- Deposit and withdraw money
- Automatic savings
- Daily, weekly, monthly and yearly saving schedules
- Goal progress tracking
- Multi-currency goal support

## Analytics

- Total expenses dashboard
- Monthly expenses statistics
- Expenses grouped by category
- Financial goals analytics

## Currency

- Multi-currency support
- Exchange rate management
- ECB and CBR exchange rate providers
- Automatic exchange rate updates
- Currency conversion service

## Family Finance

- Household management
- Household membership
- Owner, adult and child roles
- Shared household structure

## Background Tasks

- Celery integration
- Redis message broker
- Asynchronous expense notifications
- Automatic savings processing
- Scheduled exchange rate updates
- Celery Beat integration

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
- pytest-django
- Pytest Coverage
- Test Coverage: 96%

---

# 📦 Installation

## Prerequisites

Make sure you have installed:

- Git
- Docker Desktop
- Docker Compose

## Clone repository

```bash
git clone https://github.com/Evgenymokeev/finance_tracker.git

cd finance_tracker
```

## Configure environment

Create your local environment file:

Windows PowerShell:

```powershell
Copy-Item .env.example .env

```bash
cp .env.example .env
```

Generate a secure Django secret key and replace the placeholder in `.env`.

Make sure Docker Desktop is running before starting the application.

## Build and start containers

```bash
docker compose up --build -d
```

This starts the following services:

- Django REST API
- PostgreSQL
- Redis
- Celery Worker
- Celery Beat

## Apply database migrations

```bash
docker compose exec web python manage.py migrate
```

## Check application status

```bash
docker compose ps
```

## API documentation

After starting the application, the API is available at:

- API: http://localhost:8000/
- Swagger UI: http://localhost:8000/api/docs/

## Stop containers

```bash
docker compose down
```

To remove containers and the PostgreSQL volume (this deletes database data):

```bash
docker compose down -v
```

---

# 🧪 Testing

Run the test suite:

```bash
docker compose exec web pytest
```

Check Django configuration:

```bash
docker compose exec web python manage.py check
```

Check for missing migrations:

```bash
docker compose exec web python manage.py makemigrations --check --dry-run
```

---

# 🔄 Development Workflow

The project uses a feature branch workflow.

The `finance` branch is the protected integration branch.

All new features and improvements should be developed in separate feature branches.

## 1. Update the integration branch

Start by switching to the `finance` branch and pulling the latest changes:

```bash
git switch finance
git pull origin finance
```

## 2. Create a feature branch

Create a separate branch for your changes:

```bash
git switch -c feature/your-feature-name
```

Use descriptive branch names, for example:

- `feature/currency-analytics`
- `feature/family-dashboard`
- `fix/budget-calculation`

## 3. Make changes and run tests

Implement your changes and run the test suite:

```bash
docker compose exec web pytest
```

Check Django configuration:

```bash
docker compose exec web python manage.py check
```

Check for missing migrations:

```bash
docker compose exec web python manage.py makemigrations --check --dry-run
```

## 4. Commit changes

Stage and commit your changes:

```bash
git add README.md
git commit -m "Describe your changes"
```

Use clear and descriptive commit messages.

## 5. Push feature branch

Push your branch to GitHub:

```bash
git push -u origin feature/your-feature-name
```

## 6. Create a Pull Request

Open a Pull Request on GitHub:

- Base branch: `finance`
- Compare branch: `feature/your-feature-name`

GitHub Actions automatically runs CI checks for the Pull Request.

Make sure all required checks pass before merging.

## 7. Merge Pull Request

After successful CI checks and approval, merge the Pull Request using squash merging.

Delete the feature branch after merging.

---
