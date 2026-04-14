# MarzBot

<p align="center">
  <strong>VPN Subscription Manager Telegram Bot</strong><br>
  Sales, management, and Marzban panel integration
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram" alt="aiogram">
  <img src="https://img.shields.io/badge/License-AGPL--3.0-green" alt="License">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker" alt="Docker">
</p>

---

## What I Built

MarzBot is a full-featured Telegram bot for selling and managing VPN subscriptions powered by the [Marzban](https://github.com/Gozargah/Marzban) panel. It covers the entire subscription lifecycle — from browsing available plans to payment, provisioning, and renewal.

### Core Functionality

- **Multi-server Marzban management** — connect to multiple Marzban instances and distribute subscriptions across servers
- **Per-service inbound & flow configuration** — each subscription plan can have custom inbound types, network settings, and traffic limits
- **User registration & authentication** — users register via Telegram with passwordless auth, full profile management
- **Balance system** — internal wallet with top-up via payment gateways; supports balance-based purchases
- **Proxy management** — users can view, generate, and manage their proxy connections (VLESS, VMess, Trojan, Shadowsocks, etc.)
- **Admin panel** — in-bot admin interface for managing users, services, servers, and viewing stats

### Payment Integrations

- **Robokassa** — Russian payment processor (cards, SberPay, YooMoney, etc.) with full webhook handling and signature validation
- **NowPayments** — cryptocurrency payments (BTC, ETH, USDT, and 100+ coins) via their API
- **Nobitex** — Iranian crypto exchange for local crypto payments

### Subscription Purchase Flow

```
User browses plans → Selects a plan → Chooses server → Selects payment method
→ Payment gateway processes → Webhook confirms payment → Bot provisions subscription
→ User receives proxy link → Subscription active in Marzban
```

Unpaid orders are automatically cleaned up by a background scheduler.

---

## Key Implementation Details

### Auto-generated Async Marzban API Client (`marzban_client/`)

The Marzban API client is **auto-generated from the Marzban OpenAPI specification** using [datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator). This means:

- All request/response Pydantic models match the Marzban schema exactly
- Fully async — designed for concurrent operations in an aiogram bot
- When Marzban releases a new version, the client can be regenerated to stay in sync
- Zero manual API mapping — eliminates mismatch bugs between the bot and Marzban

### Socat Bridge for Marzban API Access

When Marzban runs inside Docker with only localhost exposure, the bot needs a way to reach the API. This is solved with a **socat TCP bridge** running as a systemd service:

```bash
# Exposes localhost:8000 → 0.0.0.0:8080
socat TCP-LISTEN:8080,fork,reuseaddr TCP:127.0.0.1:8000
```

- Configured as a systemd unit for auto-restart and logging
- Keeps Marzban's dashboard port closed to the internet while allowing the bot to connect
- Simple and reliable — no nginx/caddy overhead needed

### Tortoise ORM with Database Migrations

- Uses [Tortoise ORM](https://tortoise-orm.readthedocs.io/) with SQLite for zero-configuration storage
- Migrations managed with [Aerich](https://github.com/tortoise/aerich) — schema evolution without manual SQL
- Models cover: users, services, servers, proxies, orders, transactions

### ACL Middleware for Admin Panel

- Role-based access control middleware (`middlewares/`) that intercepts admin-only commands
- Checks user role before allowing access to admin handlers
- Clean separation — no permission checks scattered across handler code

### Background Jobs via APScheduler

- [APScheduler](https://apscheduler.readthedocs.io/) runs periodic cleanup tasks within the bot process
- Primary job: **purge unpaid orders** older than a configurable timeout
- Runs alongside the aiogram event loop — no separate worker process needed

### Robokassa Webhook Endpoint

- Dedicated webhook listener on **port 3333** for Robokassa payment callbacks
- Validates Robokassa signature (MD5 hash of parameters + secret key) before accepting the callback
- On successful validation: marks order as paid, provisions Marzban subscription, notifies user

### Callback Security (Hash Validation for Inline Buttons)

- Inline button callbacks include a **hash parameter** to prevent tampering
- The bot validates callback data hash before processing any button press
- Prevents users from manipulating callback payloads (e.g., changing order amounts or service IDs)

---

## Challenges & Solutions

### 1. Marzban API is Not Versioned

The Marzban API changes between releases without strict versioning. **Solution:** Auto-generating the client from the OpenAPI spec means we can regenerate on each Marzban update and get compile-time errors for any breaking changes. The generator catches model mismatches before they become runtime bugs.

### 2. Docker Networking — Bot Can't Reach Marzban

Marzban runs in its own Docker container with the dashboard bound to localhost only. The bot, running separately, can't access it. **Solution:** Instead of complex Docker networking or reverse proxies, a simple socat bridge forwards traffic from an exposed port to Marzban's localhost socket. It's a 2-line systemd unit that's battle-tested and adds zero latency.

---

## Overview

MarzBot is a Telegram bot for managing VPN subscriptions via the [Marzban](https://github.com/Gozargah/Marzban) panel. It handles service sales, user management, payment processing, and multi-server administration - all from Telegram.

> **Note:** This is the free (open-source) edition. Some advanced features are available in the premium version.

## Features

- **Multi-server Marzban integration** - connect and manage multiple Marzban instances
- **Per-service inbound & flow configuration** - customize each subscription individually
- **Crypto payment support** - built-in NowPayments and Nobitex gateways
- **User management** - registration, balance top-up, proxy management
- **Docker-ready** - one-command deployment with `docker-compose`

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Bot Framework | [aiogram 3.x](https://docs.aiogram.dev/) |
| Language | Python 3.11+ |
| Database | SQLite (via [Tortoise ORM](https://tortoise-orm.readthedocs.io/)) |
| Payments | Robokassa, NowPayments, Nobitex |
| Scheduling | [APScheduler](https://apscheduler.readthedocs.io/) |
| Migrations | [Aerich](https://github.com/tortoise/aerich) |
| Deployment | Docker / Docker Compose |
| Marzban API | Auto-generated async client (`marzban_client/`) |

## Architecture

```
marzbot/
├── app/
│   ├── handlers/       # Telegram bot command handlers (user + admin flows)
│   ├── keyboards/      # Inline & reply keyboard builders
│   ├── middlewares/     # ACL middleware (role-based access control)
│   ├── models/         # Tortoise ORM models (user, service, proxy, server, order)
│   ├── views/          # Payment gateway views & webhook handlers
│   ├── jobs/           # Background scheduled jobs (APScheduler — cleanup unpaid orders)
│   ├── utils/          # Filters, helpers, settings loader, logging config
├── marzban_client/     # Auto-generated async Marzban API client (from OpenAPI spec)
├── payment_clients/    # Payment gateway integrations (Robokassa, NowPayments, Nobitex)
├── migrations/         # Aerich database migrations
├── config.py           # Environment-based configuration loader
├── bot.py              # Application entry point
```

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/lovehrom/marzbot.git
cd marzbot

# Configure environment
cp .env.example .env
# Edit .env with your bot token and Marzban credentials

docker compose up -d
```

### Manual

```bash
pip install -r requirements.txt
python bot.py
```

## Configuration

Copy `.env.example` to `.env` and fill in:

- `BOT_TOKEN` - Telegram bot token from [@BotFather](https://t.me/BotFather)
- `MARZBAN_URL` - Your Marzban panel URL
- `MARZBAN_USERNAME` / `MARZBAN_PASSWORD` - Marzban admin credentials
- Payment gateway keys (Robokassa / NowPayments / Nobitex) - optional

## Screenshots

<!-- Add your screenshots here -->
<p align="center">
  <em>Screenshots coming soon</em>
</p>

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

Bug reports and feature requests are welcome via [Issues](https://github.com/lovehrom/marzbot/issues).

## License

This project is licensed under the [GNU AGPL-3.0](LICENSE).
