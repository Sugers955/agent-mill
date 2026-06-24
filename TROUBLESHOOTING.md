# Troubleshooting

## Backend fails to start

**Error**: `Access denied for user 'agent_mill'@'localhost'`

Check `.env` database credentials:

```
DB_USER=root
DB_PASSWORD=your_password
```

**Error**: `Address already in use :8000`

```bash
lsof -ti:8000 | xargs kill -9
./mill start
```

## Frontend build fails

**Error**: `Module not found: Can't resolve 'xxx'`

```bash
cd frontend && rm -rf node_modules && npm install
```

**Error**: TypeScript type errors

```bash
cd frontend && npx vue-tsc --noEmit
```

## Login fails

- Default credentials: `admin` / `Admin@2026`
- Check backend logs: `./mill logs`
- Ensure database is running and migrated

## Chat model returns no response

- Go to Admin → Models → check API Key is configured
- Click "Test" to verify connectivity
- Check backend logs for API errors

## File upload fails

- Check `MAX_UPLOAD_MB` in `.env` (default: 50MB)
- Check `storage/uploads/` directory exists and is writable

## Still stuck?

Open an [issue](https://github.com/Sugers955/agent-mill/issues) with:
- Error message screenshot
- Steps to reproduce
- Environment: OS, Python version, Node version, MySQL version
