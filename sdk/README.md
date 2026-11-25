# FeatureOps Python SDK and CLI

Requires Python 3.11 or newer; validated targets are 3.11-3.13. Install from this checkout with `pip install ./sdk`. The package name is `featurestore-sdk`; importing uses `featurestore`. Build/install validation does not mean the package was published.

## Lifecycle and authentication

```python
from featurestore import FeatureStoreClient, FeatureStoreError

# FEATURE_STORE_TOKEN or FEATURE_STORE_API_KEY can provide credentials.
with FeatureStoreClient(api_url="http://localhost:5173/api", timeout=10) as store:
    try:
        values = store.get_online_features(
            entity_keys=["customer_1"], features=["dev/payments:spend"]
        )
        for feature in store.iter_features():
            print(feature["name"])
    except FeatureStoreError as error:
        print(error.status_code, error.detail)  # None status for transport errors.
```

An SDK-owned HTTP client is closed by `close()` or the context manager. A supplied `session=httpx.Client(...)` remains caller-owned. Explicit `token` takes priority over `api_key`; environment variables are fallbacks. Login updates the client's JWT in memory. Configure the URL explicitly for remote deployments.

API failures expose `FeatureStoreError.status_code` and `detail`. Network/timeout failures raise the same exception with no HTTP status and retain the original cause. Requests use a finite configured timeout; there are no automatic retries of writes. A timeout can occur after the server committed, so investigate before replaying writes. Exact feature event replays are safe only when the entity/feature/event timestamp and value match.

`iter_features()` and `iter_models()` follow server pagination one page at a time. `list_features()` and `list_models()` collect all pages in memory. Use iterators for large catalogs. Stable offset ordering does not create a snapshot across concurrent catalog mutations; deduplicate or reread if exporting during edits.

Feature references accept UUID, unique name, `group:name`, or `environment/group:name`. Unknown/ambiguous references and duplicate aliases fail explicitly. Historical requests use ISO timestamps and enforce point-in-time joins; see the API's request bounds in `docs/PERFORMANCE.md` from the repository root.

## CLI credentials

```powershell
# Hidden password prompt; --show-token prints only the token for explicit capture.
$env:FEATURE_STORE_TOKEN = featurestore --url http://localhost:5173/api login --email admin@featureops.local --show-token
featurestore --url http://localhost:5173/api features
featurestore --url http://localhost:5173/api models
Remove-Item Env:FEATURE_STORE_TOKEN
```

Without `--show-token`, login prints a success message and does not print or save the token. No credentials are persisted automatically. `FEATURE_STORE_PASSWORD` is available for noninteractive login; clear it afterward. `FEATURE_STORE_API_KEY` supports service access. Global `--token` and `--api-key` options also exist; environment variables avoid credentials in shell argument history/process listings.

Available commands are `login`, `features`, `models`, and `get-online`. API and transport failures return a nonzero exit code. Library calls also support historical joins, streaming ingestion, SQL preview, artifact upload, lineage, hydration and prediction. Uploaded arbitrary bytes can be downloaded, but inference executes only the documented `featureops.linear.v1` JSON format.

Run `sh scripts/verify-sdk.sh` from the repository root in the locked Linux test environment to build/check/install the wheel and source distribution. Nothing is uploaded to a package index.
