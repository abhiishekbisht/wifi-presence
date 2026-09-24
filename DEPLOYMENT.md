# Deployment Guide: Wi-Fi Presence Estimation System

This guide outlines production deployment strategies for the Wi-Fi Presence Estimation System, including Docker containerization, Cloud PaaS (Render, Fly.io, Railway), and Bare-Metal/Linux VPS (Systemd + Nginx + Let's Encrypt SSL).

---

## 📋 Table of Contents

1. [Architecture Overview](#-architecture-overview)
2. [Option 1: Docker & Docker Compose (Recommended)](#-option-1-docker--docker-compose-recommended)
   - [Standalone Container](#11-standalone-docker-container)
   - [Docker Compose (Local/Production)](#12-docker-compose)
   - [Production with Nginx Reverse Proxy & SSL](#13-production-with-nginx-reverse-proxy--ssl)
3. [Option 2: Cloud PaaS Deployment](#-option-2-cloud-paas-deployment)
   - [Render.com](#21-rendercom)
   - [Fly.io](#22-flyio)
   - [Railway.app](#23-railwayapp)
4. [Option 3: Linux VPS Deployment (Ubuntu/Debian)](#-option-3-linux-vps-deployment-ubuntudebian)
   - [Prerequisites](#31-prerequisites)
   - [Systemd Service Setup](#32-systemd-service-setup)
   - [Nginx & SSL Configuration](#33-nginx--ssl-configuration)
5. [Database Persistence & Backup Operations](#-database-persistence--backup-operations)
6. [Health Check & Monitoring](#-health-check--monitoring)
7. [Environment Variables Reference](#-environment-variables-reference)

---

## 🏗 Architecture Overview

The system consists of:
- **Backend**: FastAPI ASGI application serving REST APIs and real-time WebSockets (`/live`).
- **Dashboard**: Static single-page dashboard assets (`/`, `/dashboard/*`).
- **Database**: SQLite database stored in `database/wifi_presence.db` (supports volume persistence).
- **ML Pipeline**: DBSCAN noise filtering and RSSI confidence calculation engine.

```
                    ┌────────────────────────┐
                    │ Internet / Campus APs  │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  Nginx Reverse Proxy   │ (SSL / WSS / Gzip / Rate Limit)
                    └───────────┬────────────┘
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      ┌─────────────────┐               ┌─────────────────┐
      │ REST API (8000) │               │ WebSocket /live │
      └────────┬────────┘               └────────┬────────┘
               │                                 │
               └────────────────┬────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  FastAPI Application   │
                    │   (ML & Sessionizer)   │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │   SQLite DB Storage    │ (Persistent Volume)
                    └────────────────────────┘
```

---

## 🐳 Option 1: Docker & Docker Compose (Recommended)

### 1.1 Standalone Docker Container

#### 1. Build the Docker Image:
```bash
docker build -t wifi-presence:latest .
```

#### 2. Run the Container with Persistent Database Storage:
```bash
docker run -d \
  --name wifi-presence \
  -p 8000:8000 \
  -v wifi_db_data:/app/database \
  -e ENVIRONMENT=production \
  -e WORKERS=2 \
  --restart unless-stopped \
  wifi-presence:latest
```

#### 3. Verify Container Status:
```bash
curl http://localhost:8000/health
```

---

### 1.2 Docker Compose

For standard deployments using `docker-compose.yml`:

```bash
# 1. Create .env from template
cp .env.production.example .env

# 2. Build and start services
docker compose up -d --build

# 3. Check logs
docker compose logs -f
```

---

### 1.3 Production with Nginx Reverse Proxy & SSL

For production setups requiring Nginx with SSL and WebSocket proxying (`docker-compose.prod.yml`):

#### 1. Prepare SSL Certificates:
Place your SSL certificate and private key in `./deploy/ssl/`:
- `./deploy/ssl/cert.pem`
- `./deploy/ssl/key.pem`

#### 2. Start the Production Stack:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

#### 3. Automated One-Command Deploy:
```bash
./deploy/scripts/deploy.sh --prod
```

---

## ☁️ Option 2: Cloud PaaS Deployment

### 2.1 Render.com

This repository includes a `render.yaml` blueprint:

1. Connect your GitHub repository to [Render](https://render.com).
2. Create a new **Blueprint Instance**.
3. Render will automatically detect `render.yaml`, configure the persistent 1GB disk at `/var/data`, and deploy.

---

### 2.2 Fly.io

This repository includes a `fly.toml` configuration:

1. Install the Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Authenticate: `fly auth login`
3. Create the persistent volume:
   ```bash
   fly volumes create wifi_data --size 1
   ```
4. Deploy the application:
   ```bash
   fly launch --no-deploy
   fly deploy
   ```

---

### 2.3 Railway.app

1. Fork or push this repository to GitHub.
2. Link your repository in [Railway](https://railway.app).
3. Railway will automatically pick up the `Procfile` and `Dockerfile`.
4. Add a persistent volume under settings and mount it to `/app/database`.

---

## 🖥 Option 3: Linux VPS Deployment (Ubuntu/Debian)

### 3.1 Prerequisites

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx sqlite3 git curl
```

Clone the repository to `/var/www/wifi-presence`:
```bash
sudo mkdir -p /var/www
sudo chown -R $USER:$USER /var/www
git clone <YOUR_REPO_URL> /var/www/wifi-presence
cd /var/www/wifi-presence
```

Create virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.production.example .env
python database/init_db.py
```

Set permissions:
```bash
sudo chown -R www-data:www-data /var/www/wifi-presence
sudo chmod -R 775 /var/www/wifi-presence/database
```

---

### 3.2 Systemd Service Setup

```bash
# 1. Copy systemd service file
sudo cp deploy/systemd/wifi-presence.service /etc/systemd/system/

# 2. Reload systemd daemon
sudo systemctl daemon-reload

# 3. Enable and start the service
sudo systemctl enable wifi-presence
sudo systemctl start wifi-presence

# 4. Check status
sudo systemctl status wifi-presence
```

---

### 3.3 Nginx & SSL Configuration

```bash
# 1. Copy Nginx site configuration
sudo cp deploy/nginx/conf.d/default.conf /etc/nginx/sites-available/wifi-presence

# 2. Update upstream in configuration if running locally:
# Change 'server backend:8000;' to 'server 127.0.0.1:8000;'

# 3. Enable site
sudo ln -s /etc/nginx/sites-available/wifi-presence /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 4. Obtain Free SSL Certificate via Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

---

## 💾 Database Persistence & Backup Operations

### Manual Backup
Run the included backup script:
```bash
./deploy/scripts/backup_db.sh
```
This produces an ACID-safe snapshot compressed with gzip in `database/backups/` without locking read/write transactions.

### Automated Nightly Backups (Cron)
Add the backup script to root crontab:
```bash
sudo crontab -e
```
Add the following line to run every midnight:
```cron
0 0 * * * /var/www/wifi-presence/deploy/scripts/backup_db.sh >> /var/log/wifi_backup.log 2>&1
```

---

## 📊 Health Check & Monitoring

- **HTTP Health Check**: `GET /health`
  - Returns `{"status":"healthy","service":"wifi-presence","version":"0.1.0"}`
  - Returns HTTP 200 when database connection and application are healthy.
- **Interactive OpenAPI Documentation**: `GET /docs`
- **Live WebSocket Stream**: `WS /live`
- **Dashboard UI**: `GET /`

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Environment mode (`production`, `development`, `testing`) |
| `HOST` | `0.0.0.0` | Network binding interface |
| `PORT` | `8000` | Port for the HTTP/WebSocket server |
| `WORKERS` | `2` | Number of worker processes (recommended: 2-4 in production) |
| `RELOAD` | `false` | Enable live code reloading (set `false` in production) |
| `DATABASE_URL` | `sqlite:////app/database/wifi_presence.db` | Database connection URI or path |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated domains or `*`) |
| `LOG_LEVEL` | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
