"""Asynchronous Ollama HTTP Client (§5.4, §5.5).

Implements:
- /api/tags, /api/show, /api/generate
- Structured output JSON Schema with graceful fallback to "json" string
- In-Python JSON schema validation with jsonschema
- Pre-flight token budget check (estimated prompt tokens + num_predict <= 0.9 * num_ctx)
- Mock transport support for testing
"""

from __future__ import annotations
import json
import logging
from typing import Any, Optional, Union
import httpx
import jsonschema

logger = logging.getLogger("h3studio.ollama")

class OllamaError(Exception):
    """Base exception for Ollama client errors."""

class TokenBudgetExceededError(OllamaError):
    """Raised when prompt + num_predict exceeds 90% of num_ctx."""

class SchemaValidationError(OllamaError):
    """Raised when structured JSON response fails schema validation."""

class ModelTruncatedError(OllamaError):
    """Raised when model stops due to context length (done_reason == 'length')."""

class OllamaGenerateResponse:
    def __init__(
        self,
        response_text: str,
        parsed_json: Optional[Any] = None,
        done_reason: str = "stop",
        total_duration: int = 0,
        prompt_eval_count: int = 0,
        eval_count: int = 0,
    ):
        self.response_text = response_text
        self.parsed_json = parsed_json
        self.done_reason = done_reason
        self.total_duration = total_duration
        self.prompt_eval_count = prompt_eval_count
        self.eval_count = eval_count

class OllamaClient:
    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        timeout_s: float = 120.0,
        connect_timeout_s: float = 5.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s
        self.connect_timeout_s = connect_timeout_s
        self.transport = transport

    def _get_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        t = httpx.Timeout(
            timeout or self.timeout_s,
            connect=self.connect_timeout_s,
        )
        return httpx.AsyncClient(
            base_url=self.endpoint,
            timeout=t,
            transport=self.transport,
        )

    def estimate_tokens(self, text: str) -> int:
        """Conservative token estimation per §5.5: len(text) / 3.2."""
        if not text:
            return 0
        return int(len(text) / 3.2)

    async def list_models(self) -> list[dict[str, Any]]:
        """GET /api/tags - list local Ollama models."""
        async with self._get_client(timeout=10.0) as client:
            resp = await client.get("/api/tags")
            if resp.status_code != 200:
                raise OllamaError(f"Ollama tags request failed ({resp.status_code}): {resp.text}")
            data = resp.json()
            return data.get("models", [])

    async def show_model(self, model_name: str) -> dict[str, Any]:
        """POST /api/show - get model metadata."""
        async with self._get_client(timeout=15.0) as client:
            resp = await client.post("/api/show", json={"name": model_name})
            if resp.status_code != 200:
                raise OllamaError(f"Ollama show request for '{model_name}' failed ({resp.status_code}): {resp.text}")
            return resp.json()

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        format: Optional[Union[dict[str, Any], str]] = None,
        options: Optional[dict[str, Any]] = None,
        keep_alive: str = "10m",
        timeout: Optional[float] = None,
    ) -> OllamaGenerateResponse:
        """
        POST /api/generate with stream: false.
        Handles preflight token check, schema fallback, and JSON validation.
        """
        opts = dict(options or {})
        num_ctx = opts.get("num_ctx", 8192)
        num_predict = opts.get("num_predict", 512)

        # Pre-flight token budget check (§5.5)
        est_tokens = self.estimate_tokens(prompt) + (self.estimate_tokens(system) if system else 0)
        if est_tokens + num_predict > 0.9 * num_ctx:
            raise TokenBudgetExceededError(
                f"Token budget exceeded: prompt estimate ({est_tokens}) + num_predict ({num_predict}) "
                f"= {est_tokens + num_predict} tokens > 90% of num_ctx ({int(0.9 * num_ctx)}). "
                f"Increase num_ctx or shorten inputs."
            )

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": opts,
        }
        if system:
            payload["system"] = system

        schema_to_validate: Optional[dict[str, Any]] = None
        if isinstance(format, dict):
            schema_to_validate = format
            payload["format"] = format
        elif format:
            payload["format"] = format

        async with self._get_client(timeout=timeout) as client:
            resp = await client.post("/api/generate", json=payload)

            # If Ollama server rejects schema object with 400/422, gracefully fall back to format: "json"
            if resp.status_code in (400, 422) and isinstance(format, dict):
                logger.warning("Ollama server rejected JSON schema in format; retrying with format: 'json'")
                payload["format"] = "json"
                resp = await client.post("/api/generate", json=payload)

            if resp.status_code != 200:
                raise OllamaError(f"Ollama generation failed ({resp.status_code}): {resp.text}")

            data = resp.json()
            raw_text = (data.get("response") or "").strip()
            done_reason = data.get("done_reason", "stop")

            if done_reason == "length":
                raise ModelTruncatedError("Model output truncated due to context/predict length (done_reason == 'length').")

            parsed_json: Optional[Any] = None
            if schema_to_validate:
                try:
                    parsed_json = json.loads(raw_text)
                except Exception as e:
                    raise SchemaValidationError(f"Model output is not valid JSON: {str(e)}\nRaw output: {raw_text[:200]}") from e

                try:
                    jsonschema.validate(instance=parsed_json, schema=schema_to_validate)
                except jsonschema.ValidationError as e:
                    raise SchemaValidationError(f"Model JSON failed schema validation: {e.message}") from e

            elif format == "json":
                try:
                    parsed_json = json.loads(raw_text)
                except Exception:
                    parsed_json = None

            return OllamaGenerateResponse(
                response_text=raw_text,
                parsed_json=parsed_json,
                done_reason=done_reason,
                total_duration=data.get("total_duration", 0),
                prompt_eval_count=data.get("prompt_eval_count", 0),
                eval_count=data.get("eval_count", 0),
            )
