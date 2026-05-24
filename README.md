# Customer Intelligence Platform

A dual-service Customer Intelligence Platform featuring XGBoost-based campaign conversion prediction and a Llama2-powered RAG engine for automated complaint resolution, built with FastAPI and Docker.

## Quick Summaries

### Architecture
The platform is orchestrated via Docker Compose, hosting two isolated FastAPI microservices. Nginx (or similar gateway) routes traffic to the Conversion and RAG APIs, while Azure Application Insights collects real-time telemetry from both services.

### Machine Learning Model (Conversion)
We utilize an **XGBoost Classifier** to predict the probability of a contact converting into a customer based on historical engagement and demographic data. It achieved an **ROC-AUC of 0.9069** and **F1 Score of 0.9924**. The model and its preprocessing schemas (LabelEncoders) are packaged into a single pickle artifact to guarantee parity between training and inference.

### Complaint Intelligence (RAG)
The Retrieval-Augmented Generation pipeline uses **FAISS** for rapid vector similarity search, mapping natural language queries to historical complaint logs embedded via `sentence-transformers`. The retrieved context is synthesized by a **LLaMA-2** model to provide concise, factual resolutions to customer support queries without hallucination.

### Monitoring & Deployment
Deployment is automated for **Azure App Services** utilizing multi-container configuration. Monitoring is deeply integrated using the `opencensus-ext-azure` package, streaming API latencies, errors, and custom ML/RAG metrics directly to **Azure Application Insights**.

---

## System Architecture

```mermaid
graph TD
    Client[Client Application / API Consumer]
    
    subrange API Gateway
        Nginx[Nginx Reverse Proxy / Load Balancer]
    end

    subgraph "Conversion Service (FastAPI)"
        ConvAPI[POST /predict]
        XGB[XGBoost Model]
        ConvAPI --> XGB
    end

    subgraph "Complaint Intelligence Service (FastAPI)"
        RAGAPI[POST /answer]
        FAISS[(FAISS Vector Store)]
        LLaMA[LLaMA2 LLM via local / API]
        RAGAPI --> FAISS
        RAGAPI --> LLaMA
    end
    
    subgraph "Monitoring & Analytics"
        AzureMonitor[Azure App Insights / Promtail]
    end

    Client -->|HTTP Requests| Nginx
    Nginx -->|Route: /conversion| ConvAPI
    Nginx -->|Route: /rag| RAGAPI
    
    ConvAPI -.->|Telemetry & Logs| AzureMonitor
    RAGAPI -.->|Telemetry & Logs| AzureMonitor

    classDef service fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef datastore fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef monitor fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;
    
    class ConvAPI,RAGAPI service;
    class FAISS,XGB datastore;
    class AzureMonitor monitor;
```

## Detailed Documentation
Please check the `docs/` directory for full technical reports:
- [Architecture](docs/architecture.md)
- [ML Model Report](docs/model_report.md)
- [RAG Report](docs/rag_report.md)
- [Monitoring Report](docs/monitoring_report.md)
