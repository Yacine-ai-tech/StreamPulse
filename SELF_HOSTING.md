# Self-Hosting StreamPulse

1. **Docker:** Standalone `docker-compose` setup.
2. **n8n Config:** Ensure n8n is running and point the webhook to `/webhook`.
3. **Security:** Export `WEBHOOK_SECRET` in both StreamPulse `.env` and n8n environment to secure events.
