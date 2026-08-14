# StreamPulse n8n Integration Guide

## Overview

This directory contains the **public integration layer** for connecting StreamPulse to n8n. These are templates and documentation that users can reuse with their own n8n instances.

## What's Included

### 1. Custom Node (`n8n_node.json`)
- **StreamPulse Webhook Node**: A drag-and-drop n8n node for pushing data to StreamPulse
- Handles HMAC signature calculation automatically
- Simplifies webhook integration for users

### 2. Workflow Templates (`workflows/`)
These are **public templates** that users can import and customize:

- **`auction_aggregator.json`**: Multi-source auction listing aggregation
- **`invoice_intake.json`**: Gmail attachment → DocIntel → StreamPulse pipeline  
- **`crm_sync.json`**: Sheet/CRM → KPI stream synchronization
- **`uptime_alert.json`**: Scheduled uptime check → email alert
- **`master_trigger.json`**: Scheduled harness that exercises other workflows

### 3. Integration Code (`n8n.py`)
- Python client for connecting StreamPulse to n8n instances
- Generic webhook bridge and REST API wrapper
- No hardcoded credentials - users provide their own

## Public vs Private Separation

### Public (This Directory - StreamPulse)
- ✅ Integration templates users can reuse
- ✅ Custom node for easy workflow building
- ✅ Documentation and examples
- ✅ Generic client code
- ❌ No private credentials
- ❌ No hardcoded API keys


## Usage for External Users

1. **Install the Custom Node**: Import `n8n_node.json` into your n8n instance
2. **Import Workflow Templates**: Use the JSON files in `workflows/` as starting points
3. **Configure Your Credentials**: Set your own API keys and endpoints
4. **Customize**: Modify workflows to match your specific use case

## StreamPulse Endpoints

These are the StreamPulse endpoints that n8n workflows can integrate with:

### Webhook Endpoints
- `POST /webhook/{source_name}` - Generic webhook receiver
- `POST /webhook/{source_name}/with-vision` - Webhook with DocIntel vision composition

### API Endpoints
- `POST /ingest/json` - Direct JSON ingestion
- `POST /ingest/csv` - CSV file upload
- `POST /ingest/email` - Gmail-style email payload

### Data Endpoints
- `GET /api/records` - Retrieve stored records
- `GET /api/stream/{source}` - SSE stream for real-time updates
- `GET /api/classification` - Classification results

## Example: Simple Webhook Integration

```json
{
  "nodes": [
    {
      "name": "StreamPulse Webhook",
      "type": "n8n-nodes-base.streamPulseWebhook",
      "parameters": {
        "url": "https://your-streampulse-instance.com/webhook/my-data",
        "secret": "your_webhook_secret"
      }
    }
  ]
}
```

## Security Notes

- Always use HTTPS endpoints in production
- Never commit webhook secrets to public repositories
- Use environment variables for sensitive configuration
- Implement proper authentication on your StreamPulse instance

## Advanced Integration Patterns

### 1. Multi-Source Aggregation
Use the `auction_aggregator.json` template as a starting point for combining data from multiple sources.

### 2. Document Processing Pipeline
The `invoice_intake.json` template shows how to combine Gmail → DocIntel → StreamPulse for document processing.

### 3. Real-Time Synchronization
The `crm_sync.json` template demonstrates keeping external systems in sync with StreamPulse data.

### 4. Monitoring and Alerting
The `uptime_alert.json` template provides a pattern for monitoring services and sending alerts.

## Contributing

When adding new integration templates:
1. Keep them generic and reusable
2. Use placeholder values for credentials
3. Include clear documentation
4. Test with multiple n8n versions if possible
5. Follow the existing naming conventions

## Support

For issues with the integration layer:
- Check StreamPulse documentation: https://github.com/Yacine-ai-tech/StreamPulse
- Review workflow template comments
- Test with the provided examples first
