# Multi-Tenant SaaS Workspace

A production-ready Full-Stack Multi-Tenant Software-as-a-Service (SaaS) application constructed using Python, Django, Django REST Framework, and Vanilla HTML/CSS/JS.

This project implements a **shared-database, shared-schema multi-tenant architecture** ensuring absolute data isolation between customer organizations. It features subscription-tier management, dynamic rate-limiting, a mockable Stripe payment gateway, user management, and a premium dark-themed dashboard served directly via Django.

---

## 🚀 Key Features

*   **Integrated Frontend Workspace (SPA):** A premium dark-mode glassmorphic client interface served directly from Django templates. Includes a landing showcase, auth forms, user directory, project dashboard, and billing portal.
*   **Robust Multi-Tenancy:** Automated data isolation using thread-safe context variables (`ContextVar`), custom middleware, and model managers. All queries are automatically scoped to the active tenant workspace.
*   **Dynamic Rate-Limiting:** Sliding-window throttle configuration using Redis. Request limits are dynamically determined on the fly based on the tenant's active subscription plan.
*   **Tiered Feature Gatekeeping:** Custom API permissions enforce plan restrictions (e.g., locking access to the analytics dashboard for standard plan users and prompting upgrades).
*   **Stripe Integration & Mocking:** Handles Stripe Checkout Sessions and processes webhook events (like payment successes and cancellations). A `MOCK_STRIPE` setting enables instant local development and upgrades without real webhook keys.
*   **Asynchronous Background Tasks:** Periodic Celery tasks to track subscription expirations and process simulated billing invoices.
*   **Custom JWT Authentication:** Extends JWT tokens to embed active tenant context (`tenant_id`, `role`, `tenant_subdomain`) directly into claims and cookies.

---

## 🛠️ Tech Stack

*   **Backend Framework:** Django (5.0) & Django REST Framework (DRF)
*   **Frontend UI:** Vanilla HTML5, Custom CSS3 (Glassmorphism design system), and Vanilla JavaScript
*   **Database:** PostgreSQL (15)
*   **Caching & Broker:** Redis (7)
*   **Background Jobs:** Celery (5.3)
*   **Payment Gateway:** Stripe (Mock & Live modes supported)
*   **Testing:** Pytest & Pytest-Django

---

## 📁 Directory Structure

```text
Multi-Tenant-Saas/ (Repository Root)
├── saas_api/
│   ├── accounts/                 # Custom user accounts, signup, roles (Admin/Member), and authentication
│   ├── api/                      # Scoped projects models, views, and tenant-only endpoints
│   ├── billing/                  # Stripe viewsets, billing invoices, payments, and background celery tasks
│   ├── config/                   # Global project configuration, settings, celery, routing
│   ├── core/                     # Shared core logic (tenants isolation middleware, base models, rate throttling)
│   ├── static/                   # Frontend assets
│   │   ├── css/style.css         # Premium dark-mode glassmorphism stylesheet
│   │   └── js/app.js             # Workspace client logic, SPA state, and API integration
│   ├── templates/                # HTML Templates folder
│   │   └── index.html            # SPA template container rendered by Django TemplateView
│   ├── tenants/                  # Tenant organizations, subscription plans, active subscriptions
│   ├── tests/                    # Backend testing suite using pytest
│   ├── manage.py                 # Django command-line tool
│   ├── pytest.ini                # Pytest configurations
│   └── requirements.txt          # Python packages list
```

---

## 🛠️ Getting Started (Local Development)

### 1. Set Up Environment Variables
Create a `.env` file inside the `saas_api` folder by copying values from the existing config or updating database settings:
```ini
DEBUG=True
SECRET_KEY=your-django-secret-key-goes-here
ALLOWED_HOSTS=localhost,127.0.0.1,.localhost

# Database Setup
DATABASE_URL=postgres://postgres:password123@127.0.0.1:5432/multi_tenant_saas

# Redis & Broker Urls
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Stripe Configuration
MOCK_STRIPE=True  # Set to False to verify real Stripe transactions
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 2. Manual Installation & Running
From the `saas_api` directory:

1. **Create and Activate Virtual Environment:**
    ```bash
    python -m venv venv
    venv\Scripts\activate   # On Windows (PowerShell: .\venv\Scripts\Activate.ps1)
    source venv/bin/activate # On Unix/macOS
    ```
2. **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3. **Execute Migrations:**
    ```bash
    python manage.py migrate
    ```
4. **Run Development Server:**
    ```bash
    python manage.py runserver
    ```

Navigate to **`http://localhost:8000/`** in your browser to view the landing page and enter the console workspace.

---

## 🧪 Running Tests

The test suite runs on `pytest` using an in-memory/sqlite database and local memory cache to keep execution completely separate from local Postgres/Redis installations.

To run tests:
1. **Activate virtual environment:**
    ```bash
    venv\Scripts\activate
    ```
2. **Execute Pytest:**
    ```bash
    pytest -v
    ```

---

## 📡 API Endpoints Reference

### 🔐 Authentication & Accounts
*   `POST /api/v1/auth/signup/` — Sign up a new Tenant & Tenant Admin.
*   `POST /api/v1/auth/login/` — Login and receive JWT access & refresh tokens.
*   `POST /api/v1/auth/token/refresh/` — Refresh access token.
*   `GET /api/v1/auth/me/` — Retrieve the current user's profile info.
*   `GET/POST/PUT/DELETE /api/v1/users/` — Manage tenant users (Admins only).

### 📁 Projects (Tenant-Scoped Data)
*   `GET/POST /api/v1/projects/` — List/Create projects.
*   `GET/PUT/DELETE /api/v1/projects/{id}/` — Retrieve/Update/Delete projects.
*   `GET /api/v1/projects/analytics/` — Premium feature (Requires `Pro` subscription).

### 💳 Billing & Subscriptions
*   `POST /api/v1/billing/subscribe/` — Upgrade or purchase a subscription plan.
*   `POST /api/v1/billing/webhook/` — Process incoming Stripe payments/events.
*   `GET /api/v1/billing/invoices/` — Retrieve past invoice summaries.
*   `GET /api/v1/billing/payments/` — Retrieve past transactions histories.
