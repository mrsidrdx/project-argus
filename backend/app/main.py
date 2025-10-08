import os
import pathlib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .telemetry.setup import setup_telemetry_and_logging
from .policy.loader import PolicyEngine
from .gateway import router as gateway_router
from .middleware import limiter


def _ensure_logs_dir() -> None:
    logs_dir = pathlib.Path(os.getenv("LOGS_DIR", "./logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)


_ensure_logs_dir()

# Initialize telemetry and structured logging before app creation
setup_telemetry_and_logging(service_name=os.getenv("SERVICE_NAME", "aegis-gateway"))

app = FastAPI(title="Aegis Gateway", version="1.0.0")

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("startup")
def on_startup() -> None:
    policy_dir = os.getenv("POLICY_DIR", "./policies")
    app.state.policy_engine = PolicyEngine(policy_directory=policy_dir)
    app.state.policy_engine.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    engine = getattr(app.state, "policy_engine", None)
    if engine is not None:
        engine.stop()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(gateway_router)


