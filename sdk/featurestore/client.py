import json
import os
from typing import Any, Dict, List, Optional
import httpx


class FeatureStoreError(Exception):
    """Base exception for Feature Store SDK errors"""
    pass


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
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 10.0,
        session: Optional[httpx.Client] = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or os.environ.get("FEATURE_STORE_API_KEY")
        self.token = token or os.environ.get("FEATURE_STORE_TOKEN")
        self.timeout = timeout
        self._session = session or httpx.Client(timeout=self.timeout)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "featurestore-python-sdk/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate using email and password, setting the session JWT Bearer token."""
        url = f"{self.api_url}/auth/login"
        res = self._session.post(url, json={"email": email, "password": password})
        if res.status_code != 200:
            raise FeatureStoreError(f"Login failed ({res.status_code}): {res.text}")
        data = res.json()
        self.token = data["access_token"]
        return data

    def get_online_features(
        self,
        entity_keys: List[str],
        features: List[str],
    ) -> Dict[str, Any]:
        """
        Fetch the latest feature values for online inference.
        
        Args:
            entity_keys: List of primary keys (e.g. user_id, device_id).
            features: List of feature names or feature UUIDs.
        Returns:
            Dictionary containing feature values mapped by entity_key.
        """
        url = f"{self.api_url}/features/online/batch"
        payload = {"entity_keys": entity_keys, "features": features}
        res = self._session.post(url, json=payload, headers=self._headers())
        if res.status_code != 200:
            raise FeatureStoreError(f"Batch online lookup failed ({res.status_code}): {res.text}")
        return res.json()

    def get_historical_features(
        self,
        observations: List[Dict[str, Any]],
        features: List[str],
    ) -> Dict[str, Any]:
        """
        Point-in-time correct join for training dataset creation.
        
        Args:
            observations: List of dicts with 'entity_key' and 'event_time' (ISO string).
            features: List of feature names to join.
        """
        url = f"{self.api_url}/features/offline/as-of-join"
        payload = {"observations": observations, "features": features}
        res = self._session.post(url, json=payload, headers=self._headers())
        if res.status_code != 200:
            raise FeatureStoreError(f"As-of join failed ({res.status_code}): {res.text}")
        return res.json()

    def stream_ingest(
        self,
        records: List[Dict[str, Any]],
        persist_offline: bool = True,
    ) -> Dict[str, Any]:
        """
        Push streaming real-time feature events directly into the online store.
        """
        url = f"{self.api_url}/features/stream-ingest"
        payload = {"records": records, "persist_offline": persist_offline}
        res = self._session.post(url, json=payload, headers=self._headers())
        if res.status_code != 201:
            raise FeatureStoreError(f"Stream ingest failed ({res.status_code}): {res.text}")
        return res.json()

    def list_features(self) -> List[Dict[str, Any]]:
        """List all registered feature definitions."""
        url = f"{self.api_url}/features"
        res = self._session.get(url, headers=self._headers())
        if res.status_code != 200:
            raise FeatureStoreError(f"List features failed ({res.status_code}): {res.text}")
        return res.json()

    def list_models(self) -> List[Dict[str, Any]]:
        """List all models registered in the model registry."""
        url = f"{self.api_url}/models"
        res = self._session.get(url, headers=self._headers())
        if res.status_code != 200:
            raise FeatureStoreError(f"List models failed ({res.status_code}): {res.text}")
        return res.json()

    def upload_artifact(
        self,
        model_id: str,
        version_id: str,
        file_path: str,
    ) -> Dict[str, Any]:
        """Upload a model artifact binary file (.pkl, .onnx, .tar.gz)."""
        url = f"{self.api_url}/models/{model_id}/versions/{version_id}/artifact"
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            headers = {k: v for k, v in self._headers().items() if k != "Content-Type"}
            res = self._session.post(url, files=files, headers=headers)
        if res.status_code != 200:
            raise FeatureStoreError(f"Upload artifact failed ({res.status_code}): {res.text}")
        return res.json()
