"""
StreamPulse declarative sources via dlt.

Each @dlt.source is a generator of KPI records that the dlt pipeline can
incrementally load into PostgreSQL or DuckDB. Wire to Prefect for scheduling.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

try:
    import dlt  # type: ignore
    _DLT = True
except ImportError:
    _DLT = False


if _DLT:
    @dlt.source(name="gmail_source")
    def gmail_source(query: str = "label:invoices is:unread") -> Iterable[Dict[str, Any]]:
        """Yield parsed invoice metadata from Gmail."""
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            
            # Look for standard token file
            creds = None
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            
            if creds:
                service = build('gmail', 'v1', credentials=creds)
                results = service.users().messages().list(userId='me', q=query).execute()
                messages = results.get('messages', [])
                
                for message in messages:
                    msg = service.users().messages().get(userId='me', id=message['id']).execute()
                    yield {
                        "id": msg['id'],
                        "snippet": msg['snippet'],
                        "labels": msg.get('labelIds', []),
                        "source": "gmail"
                    }
        except ImportError:
            pass
        return []  # type: ignore

    @dlt.source(name="gsheet_source")
    def gsheet_source(sheet_id: str = "", range_name: str = "Sheet1!A1:Z") -> Iterable[Dict[str, Any]]:
        """Yield rows from a Google Sheet."""
        if not sheet_id:
            return [] # type: ignore
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            
            creds = None
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/spreadsheets.readonly'])
                
            if creds:
                service = build('sheets', 'v4', credentials=creds)
                sheet = service.spreadsheets()
                result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
                values = result.get('values', [])
                
                if values and len(values) > 1:
                    headers = values[0]
                    for row in values[1:]:
                        yield {headers[i]: row[i] if i < len(row) else None for i in range(len(headers))}
        except ImportError:
            pass
        return []  # type: ignore

    @dlt.source(name="webhook_source")
    def webhook_source(records: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        """Pass through pre-collected webhook records."""
        for r in records or []:
            yield r
else:
    def gmail_source(*a, **kw): return []
    def gsheet_source(*a, **kw): return []
    def webhook_source(records=None, *a, **kw): return records or []
