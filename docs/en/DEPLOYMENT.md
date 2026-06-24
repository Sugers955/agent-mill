# Deployment Guide

This document provides the complete deployment guide for Agent Mill, including Docker one-click deployment and manual deployment.

---

## Table of Contents

- [System Requirements](#system-requirements)
- [Docker Deployment (Recommended)](#docker-deployment-recommended)
- [Manual Deployment](#manual-deployment)
- [Environment Variables](#environment-variables)
- [FAQ](#faq)

---

## System Requirements

### Minimum Configuration

| Resource | Requirement |
|----------|-------------|
| CPU | 2 cores |
| Memory | 4 GB |
| Disk | 20 GB SSD |
| OS | Linux / macOS / Windows (WSL2) |

### Recommended Configuration

| Resource | Requirement |
|----------|-------------|
| CPU | 4 cores |
| Memory | 8 GB |
| Disk | 50 GB SSD |
| OS | Ubuntu 22.04+ / CentOS 8+ |

### Software Dependencies

| Software | Version |
|----------|---------|
| Docker | 24.0+ |
| Docker Compose | v2.20+ |
| Python | 3.11+ |
| Node.js | 18+ |
| MySQL | 8.0+ |

---

## Docker Deployment (Recommended)

### 1. Get the Code

```bash
git clone https://github.com/Sugers955/agent-mill.git
cd agent-mill
```

### 2. Configure Environment Variables

```bash
# Copy environment variable template
cp .env.example .env

# Edit environment variables
vim .env
```

### 3. Required Variables

```bash
# Database configuration
DB_HOST=mysql
DB_PORT=3306
DB_USER=agent_mill
DB_PASSWORD=your_secure_password
DB_NAME=agent_mill

# Security configuration
JWT_SECRET=your-random-secret-key-at-least-32-chars
ENCRYPTION_KEY=your-fernet-key

# AI model configuration (configure at least one)
ANTHROPIC_API_KEY=sk-ant-xxx
# or
OPENAI_API_KEY=sk-xxx

# Seed user passwords
SEED_ADMIN_PASSWORD=admin123
SEED_USER_PASSWORD=user123
```

### 4. Start Services

```bash
# First deployment
make deploy

# Or use docker compose directly
docker compose up -d
```

### 5. Verify Deployment

```bash
# Check service status
make deploy-status

# View logs
make deploy-logs

# Access the application
# http://localhost
```

### 6. Common Commands

```bash
# Start
make deploy

# Stop (preserve data)
make deploy-down

# Stop and delete data (dangerous!)
docker compose down -v

# Redeploy after code updates
make deploy-update

# View real-time logs
docker compose logs -f api
docker compose logs -f web
```

---

## Manual Deployment

### 1. Install Dependencies

#### Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Build production version
npm run build
```

### 2. Configure Database

```sql
-- Login to MySQL
mysql -u root -p

-- Create database
CREATE DATABASE agent_mill CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user
CREATE USER 'agent_mill'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON agent_mill.* TO 'agent_mill'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Configure Backend

```bash
cd backend

# Configure environment variables
cp .env.example .env
# Edit the .env file

# Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Configure Frontend

```bash
cd frontend

# Configure Nginx or use Vite dev server
npm run dev  # Development environment
# or
npm run build && npx serve dist  # Production preview
```

### 5. Configure Reverse Proxy (Production)

#### Nginx Configuration Example

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Frontend static files
    location / {
        root /path/to/agent-mill/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

---

## Environment Variables

### Complete Variable List

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | Yes | localhost | Database host |
| `DB_PORT` | No | 3306 | Database port |
| `DB_USER` | Yes | root | Database user |
| `DB_PASSWORD` | Yes | - | Database password |
| `DB_NAME` | Yes | agent_mill | Database name |
| `JWT_SECRET` | Yes | - | JWT signing key (at least 32 chars) |
| `ENCRYPTION_KEY` | Yes | - | Fernet encryption key |
| `ANTHROPIC_API_KEY` | Recommended | - | Anthropic API Key (configure at least one) |
| `OPENAI_API_KEY` | Recommended | - | OpenAI API Key (configure at least one) |
| `SEED_ADMIN_PASSWORD` | No | admin123 | Admin initial password |
| `SEED_USER_PASSWORD` | No | user123 | Regular user initial password |
| `DEBUG` | No | false | Debug mode |
| `CORS_ORIGINS` | No | * | CORS allowed origins |

### Generate Secure Keys

```bash
# Generate JWT key
openssl rand -hex 32

# Generate Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## FAQ

### 1. Database Connection Failed

**Symptom**: `Can't connect to MySQL server`

**Solution**:

```bash
# Check if MySQL is running
docker compose ps mysql

# Check database configuration
cat .env | grep DB_

# Test connection
mysql -h localhost -u agent_mill -p
```

### 2. Invalid API Key

**Symptom**: `Authentication failed` or `Invalid API key`

**Solution**:

```bash
# Check API Key configuration
cat .env | grep API_KEY

# Test API Key
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" https://api.anthropic.com/v1/messages
```

### 3. Insufficient Memory

**Symptom**: `OOMKilled` or `MemoryError`

**Solution**:

```bash
# View container resource usage
docker stats

# Increase memory limit (docker-compose.yml)
services:
  api:
    deploy:
      resources:
        limits:
          memory: 4G
```

### 4. Port Conflict

**Symptom**: `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solution**:

```bash
# Check port usage
lsof -i :8000

# Modify port mapping (docker-compose.yml)
services:
  api:
    ports:
      - "8001:8000"
```

### 5. File Upload Failed

**Symptom**: `413 Request Entity Too Large`

**Solution**:

```bash
# Nginx configuration
client_max_body_size 100M;

# Check disk space
df -h
```

---

## Production Recommendations

### Security Recommendations

1. Use HTTPS (via Let's Encrypt or commercial certificates)
2. Configure firewall, open only necessary ports
3. Regularly update system and dependencies
4. Back up database and user uploaded files
5. Enable audit log monitoring

### Performance Recommendations

1. Use SSD storage
2. Configure Redis caching (optional)
3. Use CDN for static assets
4. Configure load balancing (multi-instance deployment)

### Monitoring Recommendations

1. Configure log collection (ELK / Loki)
2. Set up performance monitoring (Prometheus + Grafana)
3. Configure alert notifications (DingTalk / WeCom / Feishu)

---

## Getting Help

If you encounter issues, get help through:

- [GitHub Issues](https://github.com/Sugers955/agent-mill/issues)
- [GitHub Discussions](https://github.com/Sugers955/agent-mill/discussions)
- Submit a new Issue or Discussion
