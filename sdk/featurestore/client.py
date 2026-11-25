import os
from typing import Any

import httpx


class FeatureStoreError(Exception):
    """Base exception for Feature Store SDK errors"""

    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class FeatureStoreClient:
    """
    Client for interacting with the Feature Store & Model Registry API.

    Usage:
        client = FeatureStoreClient(
            api_url="http://localhost:8000",
            api_key="fo_your_api_key_here"
        )

        # Real-time online feature lookup
        features = client.get_online_features(
            entity_keys=["cust_001", "cust_002"],
            features=["customer_30d_spend"]
        )
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 10.0,
        session: httpx.Client | None = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or os.environ.get("FEATURE_STORE_API_KEY")
        self.token = token or os.environ.get("FEATURE_STORE_TOKEN")
        self.timeout = timeout
        self._owns_session = session is None
        self._session = session if session is not None else httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        """Close an owned HTTP client. Caller-supplied sessions remain open."""
        if self._owns_session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _request(self, method: str, url: str, **kwargs):
        kwargs.setdefault("headers", self._headers())
        try:
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
        except httpx.RequestError as exc:
            raise FeatureStoreError(f"API transport failed: {type(exc).__name__}") from exc
        if not response.is_success:
            try:
                detail = response.json().get("detail", "API request failed")
            except (ValueError, AttributeError):
                detail = "API returned a non-JSON error"
            raise FeatureStoreError(
                f"API request failed ({response.status_code}): {str(detail)[:500]}",
                status_code=response.status_code,
                detail=detail,
            )
        return response

    def _list(self, endpoint: str):
        """Yield bounded pages; callers may stop without downloading the full catalog."""
        offset = 0
        while True:
            response = self._request(
                "GET", f"{self.api_url}/{endpoint}", params={"limit": 500, "offset": offset}
            )
            yield from response.json()
            next_offset = response.headers.get("X-Next-Offset")
            if next_offset is None:
                break
            try:
                following = int(next_offset)
            except ValueError as exc:
                raise FeatureStoreError("Invalid pagination offset") from exc
            if following <= offset:
                raise FeatureStoreError("Pagination did not advance")
            offset = following

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "featurestore-python-sdk/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate using email and password, setting the session JWT Bearer token."""
        url = f"{self.api_url}/auth/login"
        res = self._request("POST", url, json={"email": email, "password": password})
        data = res.json()
        self.token = data["access_token"]
        return data

    def get_online_features(
        self,
        entity_keys: list[str],
        features: list[str],
    ) -> dict[str, Any]:
        """
        Fetch the latest feature values for online inference.

        Args:
            entity_keys: List of primary keys (e.g. user_id, device_id).
            features: UUIDs, unique names, group:name or environment/group:name references.
        Returns:
            Dictionary containing feature values mapped by entity_key.
        """
        url = f"{self.api_url}/features/online/batch"
        payload = {"entity_keys": entity_keys, "features": features}
        res = self._request("POST", url, json=payload, headers=self._headers())
        return res.json()

    def get_historical_features(
        self,
        observations: list[dict[str, Any]],
        features: list[str],
    ) -> dict[str, Any]:
        """
        Point-in-time correct join for training dataset creation.

        Args:
            observations: List of dicts with 'entity_key' and 'event_time' (ISO string).
            features: List of feature names to join.
        """
        url = f"{self.api_url}/features/offline/as-of-join"
        payload = {"observations": observations, "features": features}
        res = self._request("POST", url, json=payload, headers=self._headers())
        return res.json()

    def stream_ingest(
        self,
        records: list[dict[str, Any]],
        persist_offline: bool = True,
    ) -> dict[str, Any]:
        """
        Push streaming real-time feature events directly into the online store.
        """
        url = f"{self.api_url}/features/stream-ingest"
        payload = {"records": records, "persist_offline": persist_offline}
        res = self._request("POST", url, json=payload, headers=self._headers())
        return res.json()

    def iter_features(self):
        """Iterate features page by page, following server continuation headers."""
        return self._list("features")

    def list_features(self) -> list[dict[str, Any]]:
        """Collect all pages; use iter_features for large catalogs."""
        return list(self.iter_features())

    def iter_models(self):
        return self._list("models")

    def list_models(self) -> list[dict[str, Any]]:
        return list(self.iter_models())

    def upload_artifact(
        self,
        model_id: str,
        version_id: str,
        file_path: str,
    ) -> dict[str, Any]:
        """Upload artifact bytes. Only featureops.linear.v1 JSON supports inference."""
        url = f"{self.api_url}/models/{model_id}/versions/{version_id}/artifact"
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            headers = {k: v for k, v in self._headers().items() if k != "Content-Type"}
            res = self._request("POST", url, files=files, headers=headers)
        return res.json()

    def dry_run_query(self, query: str, limit: int = 10) -> dict[str, Any]:
        """Preview and validate feature SQL transformation query results."""
        url = f"{self.api_url}/features/dry-run"
        res = self._request(
            "POST", url, json={"query": query, "limit": limit}, headers=self._headers()
        )
        return res.json()

    def get_feature_lineage(self, feature_id: str) -> dict[str, Any]:
        """Get the visual DAG dependency graph for a feature."""
        url = f"{self.api_url}/features/{feature_id}/lineage-graph"
        res = self._request("GET", url, headers=self._headers())
        return res.json()

    def get_model_lineage(self, model_id: str) -> dict[str, Any]:
        """Get the visual DAG dependency graph for a model."""
        url = f"{self.api_url}/models/{model_id}/lineage-graph"
        res = self._request("GET", url, headers=self._headers())
        return res.json()

    def hydrate_model_features(
        self,
        model_id: str,
        entity_keys: list[str],
        version: str | None = None,
    ) -> dict[str, Any]:
        """Hydrate online features for the specified model in real time."""
        url = f"{self.api_url}/models/{model_id}/hydrate"
        payload = {"entity_keys": entity_keys, "version": version}
        res = self._request("POST", url, json=payload, headers=self._headers())
        return res.json()

    def predict(
        self,
        model_id: str,
        entity_key: str,
        runtime_features: dict[str, Any] | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        """
        Real-time model inference proxy:
        Hydrates latest online features, combines runtime features, and returns scored prediction.
        """
        url = f"{self.api_url}/models/{model_id}/predict"
        payload = {
            "entity_key": entity_key,
            "version": version,
            "runtime_features": runtime_features or {},
        }
        res = self._request("POST", url, json=payload, headers=self._headers())
        return res.json()
