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


def test_sdk_client_dry_run_and_lineage(client, admin_token):
    sdk_client = FeatureStoreClient(
        api_url="http://testserver",
        token=admin_token,
        session=client
    )
    # Dry run
    dry_res = sdk_client.dry_run_query("SELECT 100 as test_col", limit=1)
    assert dry_res["is_valid"] is True
    assert "test_col" in dry_res["columns"]

    # Features & lineage
    feats = sdk_client.list_features()
    assert feats, "Required fixture data is missing"
    lin = sdk_client.get_feature_lineage(str(feats[0]["id"]))
    assert "nodes" in lin
    assert "edges" in lin


def test_sdk_client_hydrate_and_predict(client, admin_token):
    sdk_client = FeatureStoreClient(
        api_url="http://testserver",
        token=admin_token,
        session=client
    )
    models = [model for model in sdk_client.list_models() if model["name"] == "Churn Predictor"]
    assert models, "Required fixture data is missing"
    m_id = str(models[0]["id"])
    hyd = sdk_client.hydrate_model_features(m_id, entity_keys=["cust_001"])
    assert "hydrated_records" in hyd

    pred = sdk_client.predict(m_id, entity_key="cust_001", runtime_features={})
    assert "prediction" in pred
    assert "probability" in pred["prediction"]
