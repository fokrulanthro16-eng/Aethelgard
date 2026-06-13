# Aethelgard Backend

FastAPI service for the Aethelgard Digital Legacy Vault.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
pytest tests/ -v
```
