# End-to-End Examples

This directory contains real-world runnable tutorials showing how to use the **Feature Store & Model Registry** across the complete machine learning lifecycle.

---

## 1. Customer Churn Prediction (`01_churn_prediction_e2e.py`)

A complete script demonstrating:
1. **SDK Authentication**: Connecting to the Feature Store via API key or JWT Bearer.
2. **Streaming Feature Ingestion**: Pushing real-time event updates to the online store.
3. **Leakage-Free Point-in-Time Join**: Generating training datasets with `get_historical_features()`.
4. **Model Training**: Fitting a classification model with `scikit-learn`.
5. **Model Registry & Artifact Storage**: Versioning the model and uploading serialized weights.
6. **Online Feature Hydration & Real-Time Inference**: Low-latency feature lookups and model scoring via the prediction proxy.
7. **Lineage DAG & Drift Monitoring**: Verifying upstream feature dependencies and tracking PSI drift.

### Running the Example

Make sure the backend is running (`uvicorn app.main:app --port 8000`):

```bash
# Install scikit-learn (optional, for actual fitting)
pip install scikit-learn

# Run the end-to-end pipeline
python examples/01_churn_prediction_e2e.py
```
