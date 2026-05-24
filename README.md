# Week 13 – Customer Intelligence Platform

A dual-service ML platform for customer intelligence, consisting of:

1. **Conversion Prediction Service** – XGBoost model trained on campaign data, served via FastAPI `POST /predict`
2. **Complaint Intelligence RAG Service** – FAISS vector store over complaint documents, answered by a local Llama 2 model via FastAPI `POST /answer`

Both services are containerised and can be deployed locally with Docker Compose or to Azure App Service (multicontainer).

---

## Model Results

| Metric | Value |
|--------|-------|
| ROC-AUC | **0.8828** |
| F1 Score | **0.9924** |
| Training rows | 2,000 |
| Features | 11 (7 numeric + 4 categorical) |

---

## Quick-Start (Local, No Docker)

```bash
# 1. Generate sample data
python scripts/generate_sample_data.py

# 2. Train the XGBoost model
python services/conversion/train.py

# 3. Start the Conversion Prediction Service (port 8000)
uvicorn services.conversion.main:app --host 0.0.0.0 --port 8000

# 4. Start the RAG Complaint Intelligence Service (port 8001)
uvicorn services.rag.main:app --host 0.0.0.0 --port 8001

# 5. Run verification checks
python scripts/verify.py
```

### Test the API

```bash
# Health check
curl http://localhost:8000/health

# Conversion prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":35,"income":55000,"num_campaigns":3,"channel":"email","gender":"M"}'

# Complaint intelligence
curl -X POST http://localhost:8001/answer \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the most common billing complaints?"}'
```

---

## Quick-Start (Docker Compose)

```bash
# Build images and start both services
docker compose up --build
```

- Conversion service → `http://localhost:8000`  (docs at `/docs`)
- RAG service → `http://localhost:8001`  (docs at `/docs`)

---

## Deployment (Azure)

```bash
# Authenticate
az login

# Deploy resources + push images
./infra/azure_deploy.sh
```

See [`infra/azure_deploy.sh`](infra/azure_deploy.sh) for detailed steps (ACR, App Service Plan, multicontainer config).

---

## Directory Layout

```
Weel13_Project/
├─ data/
│   ├─ campaign/            # campaign_data.csv (2 000 rows generated)
│   └─ complaints/          # complaint_0001.txt … complaint_0100.txt
├─ models/
│   ├─ conversion_model.pkl # trained XGBoost artifact
│   └─ train_metrics.json   # ROC-AUC + F1 from last training run
├─ rag/                     # Llama 2 checkpoint & FAISS index (gitignored)
├─ scripts/
│   ├─ generate_sample_data.py
│   └─ verify.py            # standalone end-to-end verification script
├─ services/
│   ├─ conversion/
│   │   ├─ train.py         # XGBoost training pipeline
│   │   └─ main.py          # FastAPI prediction service
│   └─ rag/
│       ├─ rag_engine.py    # FAISS index + Llama 2 inference
│       └─ main.py          # FastAPI answer service
├─ docker/
│   ├─ Dockerfile.base
│   ├─ Dockerfile.conversion
│   └─ Dockerfile.rag
├─ infra/
│   └─ azure_deploy.sh
├─ monitoring/
│   └─ azure_monitor.py
├─ tests/
│   ├─ test_conversion.py   # unit tests (xgboost mocked)
│   └─ test_rag.py          # unit tests (LLM + FAISS mocked)
├─ docker-compose.yml
├─ requirements.txt
└─ pytest.ini
```

---

## API Reference

### Conversion Service  (`http://localhost:8000`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Returns service health + model load status |
| `/predict` | POST | Returns `conversion_prob` [0-1] + binary `prediction` |
| `/docs` | GET | Interactive Swagger UI |

**Predict request body:**
```json
{
  "age": 35, "income": 55000, "num_campaigns": 3,
  "num_clicks": 7, "num_opens": 12, "recency_days": 14,
  "tenure_days": 365, "gender": "M", "channel": "email",
  "product_category": "electronics", "region": "north"
}
```

### RAG Service  (`http://localhost:8001`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Returns service health + index status |
| `/answer` | POST | Returns LLM answer + cited source chunks |
| `/docs` | GET | Interactive Swagger UI |

**Answer request body:**
```json
{ "query": "What are the most common billing complaints?", "top_k": 5 }
```

---

*All code includes type hints, docstrings, structured logging, and Azure Monitor telemetry hooks.*
