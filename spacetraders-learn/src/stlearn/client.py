"""Rate-limited SpaceTraders HTTP client with retries and pagination."""

from __future__ import annotations

import time
from typing import Any, Iterator

import httpx
from rich.console import Console

console = Console()


class SpaceTradersError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class SpaceTradersClient:
    """Thin client that models production API ingestion habits.

    - Respects X-RateLimit-* / Retry-After headers
    - Retries transient failures with backoff
    - Paginates list endpoints via meta.page / meta.total
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        min_interval: float = 0.55,
    ) -> None:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout)
        self._min_interval = min_interval
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SpaceTradersClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        attempts = 0
        while True:
            attempts += 1
            self._throttle()
            response = self._client.request(method, path, **kwargs)
            self._last_request = time.monotonic()

            if response.status_code == 429 or response.status_code >= 500:
                retry_after = float(response.headers.get("Retry-After", "1"))
                if attempts >= 6:
                    raise SpaceTradersError(
                        f"Gave up after retries: {response.status_code}",
                        status=response.status_code,
                        body=_safe_json(response),
                    )
                wait = max(retry_after, 0.5 * attempts)
                console.log(f"[yellow]retry[/] {method} {path} status={response.status_code} sleep={wait:.1f}s")
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                raise SpaceTradersError(
                    f"API error {response.status_code} for {method} {path}",
                    status=response.status_code,
                    body=_safe_json(response),
                )

            payload = response.json()
            return payload if isinstance(payload, dict) else {"data": payload}

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("POST", path, **kwargs)

    def paginate(
        self,
        path: str,
        *,
        limit: int = 20,
        max_pages: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        page = 1
        params = dict(params or {})
        while True:
            params.update({"page": page, "limit": limit})
            payload = self.get(path, params=params)
            rows = payload.get("data") or []
            for row in rows:
                yield row
            meta = payload.get("meta") or {}
            total = int(meta.get("total") or 0)
            limit_used = int(meta.get("limit") or limit)
            if not rows:
                break
            if page * limit_used >= total:
                break
            page += 1
            if max_pages is not None and page > max_pages:
                break


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text
