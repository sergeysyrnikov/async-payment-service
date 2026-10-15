"""Tiny webhook receiver for manual testing: prints every POST payload.

Usage:
    uv run python scripts/webhook_receiver.py [port]   # default port 9000
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        print(f"\n--- WEBHOOK POST {self.path} ---", flush=True)
        try:
            print(json.dumps(json.loads(raw), indent=2, ensure_ascii=False), flush=True)
        except json.JSONDecodeError:
            print(raw.decode(errors="replace"), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # silence the default access log


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    print(f"Webhook receiver listening on http://localhost:{port}", flush=True)
    HTTPServer(("0.0.0.0", port), WebhookHandler).serve_forever()


if __name__ == "__main__":
    main()
