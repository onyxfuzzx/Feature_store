from featurestore import FeatureStoreClient
from app.core.config import settings


def test_sdk_client_online_features(client, admin_token):
    sdk_client = FeatureStoreClient(
        api_url="http://testserver",
        token=admin_token,
        session=client
    )
    res = sdk_client.get_online_features(
        entity_keys=["cust_001"],
        features=["customer_30d_spend"]
    )
    assert "values" in res
    assert "read_latency_ms" in res
    assert "cust_001" in res["values"]


def test_sdk_client_historical_features(client, admin_token):
    from datetime import datetime
    sdk_client = FeatureStoreClient(
        api_url="http://testserver",
        token=admin_token,
        session=client
    )
    res = sdk_client.get_historical_features(
        observations=[{"entity_key": "cust_001", "event_time": datetime.utcnow().isoformat()}],
        features=["customer_30d_spend"]
    )
    assert "joined_rows" in res
    assert res["row_count"] == 1


def test_sdk_client_list_features(client, admin_token):
    sdk_client = FeatureStoreClient(
        api_url="http://testserver",
        token=admin_token,
        session=client
    )
    feats = sdk_client.list_features()
    assert isinstance(feats, list)
    assert len(feats) >= 1
