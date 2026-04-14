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

## Overview

MarzBot is a Telegram bot for managing VPN subscriptions via the [Marzban](https://github.com/Gozargah/Marzban) panel. It handles service sales, user management, payment processing, and multi-server administration — all from Telegram.

> **Note:** This is the free (open-source) edition. Some advanced features are available in the premium version.

## Features

- **Multi-server Marzban integration** — connect and manage multiple Marzban instances
- **Per-service inbound & flow configuration** — customize each subscription individually
- **Crypto payment support** — built-in NowPayments and Nobitex gateways
- **User management** — registration, balance top-up, proxy management
- **Docker-ready** — one-command deployment with `docker-compose`

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Bot Framework | [aiogram 3.x](https://docs.aiogram.dev/) |
| Language | Python 3.11+ |
| Database | SQLite (via [ Tortoise ORM](https://tortoise-orm.readthedocs.io/)) |
| Payments | NowPayments, Nobitex |
| Deployment | Docker / Docker Compose |
| Marzban API | Custom async client (`marzban_client/`) |

## Architecture

```
marzbot/
├── app/
│   ├── handlers/       # Telegram bot command handlers
│   ├── keyboards/      # Inline & reply keyboards
│   ├── middlewares/    # ACL & auth middleware
│   ├── models/         # Database models (user, service, proxy, server)
│   ├── views/          # Payment views
│   ├── jobs/           # Background jobs (cleanup unpaid)
│   └── utils/          # Filters, helpers, settings, logging
├── marzban_client/     # Async Marzban API client (auto-generated models)
├── payment_clients/    # Payment gateway integrations
├── migrations/         # Database migrations
└── config.py           # Configuration loader
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

- `BOT_TOKEN` — Telegram bot token from [@BotFather](https://t.me/BotFather)
- `MARZBAN_URL` — Your Marzban panel URL
- `MARZBAN_USERNAME` / `MARZBAN_PASSWORD` — Marzban admin credentials
- Payment gateway keys (NowPayments / Nobitex) — optional

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
