# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""HTTP client for the Cambridge PledgeTracker queue API.

The pledge pipeline (Vertex search + LLM event extraction) runs on a GPU
endpoint that handles one request at a time; a run takes ~3 minutes. The API is
therefore an async job queue: submit a job, get an id, poll until done. Results
are stored server-side, so a finished job's result can be re-fetched any time
without re-running the pipeline.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://pledgequeue.ramialy.com"

_REQUEST_TIMEOUT_S = 30
_TRANSIENT_RETRIES = 3
_TRANSIENT_BACKOFF_S = 5.0


class PledgeQueueError(RuntimeError):
    """Raised for non-recoverable queue API failures (auth, bad input, failed job)."""


class PledgeJobFailedError(PledgeQueueError):
    """Raised when the pipeline reports a job as failed."""


class PledgeJobTimeoutError(PledgeQueueError):
    """Raised when a job does not reach a terminal state within the timeout."""


class PledgeQueueClient:
    """Thin synchronous client for the PledgeTracker queue API.

    Auth: every request except /health carries the ``X-Api-Key`` header. The key
    is read from ``PLEDGETRACKER_API_KEY`` and never logged.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = (
            base_url or os.getenv("PLEDGETRACKER_API_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._api_key = api_key or os.getenv("PLEDGETRACKER_API_KEY") or ""
        if not self._api_key:
            raise PledgeQueueError(
                "PLEDGETRACKER_API_KEY is not set. Add it to ai-backend/.env "
                "(the file is gitignored — never commit the key)."
            )
        self._sleep = sleep

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def health(self) -> bool:
        """GET /health — no API key required; returns True when the service is up."""
        try:
            response = requests.get(
                f"{self._base_url}/health", timeout=_REQUEST_TIMEOUT_S
            )
        except requests.RequestException:
            return False
        return response.ok

    def submit_job(self, inputs: dict[str, Any]) -> int:
        """POST /jobs — submit one pledge run; returns the job id immediately."""
        payload = self._request("POST", "/jobs", json={"inputs": inputs})
        job_id = payload.get("id")
        if not isinstance(job_id, int):
            raise PledgeQueueError(f"POST /jobs returned no job id: {payload!r}")
        logger.info(
            "PledgeTracker job %s submitted (status=%s position=%s)",
            job_id,
            payload.get("status"),
            payload.get("position"),
        )
        return job_id

    def get_job(self, job_id: int) -> dict[str, Any]:
        """GET /jobs/{id} — current job state (queued | running | done | failed)."""
        return self._request("GET", f"/jobs/{job_id}")

    def wait_for_job(
        self,
        job_id: int,
        *,
        poll_interval_s: float = 10.0,
        timeout_s: float = 1800.0,
    ) -> dict[str, Any]:
        """Poll a job until it is done; return its ``result`` payload.

        A run normally takes ~3 minutes, but the first job after the GPU
        endpoint has been idle can take several minutes longer while it boots —
        hence the generous default timeout.

        Raises:
            PledgeJobFailedError: the pipeline reported the job as failed.
            PledgeJobTimeoutError: no terminal state within ``timeout_s``.
        """
        deadline = time.monotonic() + timeout_s
        while True:
            job = self.get_job(job_id)
            status = job.get("status")

            if status == "done":
                result = job.get("result")
                if not isinstance(result, dict):
                    raise PledgeQueueError(
                        f"Job {job_id} is done but carries no result payload."
                    )
                return result
            if status == "failed":
                raise PledgeJobFailedError(
                    f"Job {job_id} failed: {job.get('error') or 'no error detail'}"
                )

            if status == "running":
                logger.info(
                    "PledgeTracker job %s running for %ss",
                    job_id,
                    job.get("running_for_s"),
                )
            else:
                logger.info(
                    "PledgeTracker job %s queued (position=%s)",
                    job_id,
                    job.get("position"),
                )

            if time.monotonic() >= deadline:
                raise PledgeJobTimeoutError(
                    f"Job {job_id} did not finish within {timeout_s:.0f}s "
                    f"(last status: {status})."
                )
            self._sleep(poll_interval_s)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """One authenticated request with a short retry on transient errors."""
        url = f"{self._base_url}{path}"
        headers = {"X-Api-Key": self._api_key}
        last_exc: Optional[Exception] = None

        for attempt in range(1, _TRANSIENT_RETRIES + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    timeout=_REQUEST_TIMEOUT_S,
                    **kwargs,
                )
            except requests.RequestException as exc:
                # Connection-level failure — retry with a flat backoff.
                last_exc = exc
                if attempt < _TRANSIENT_RETRIES:
                    self._sleep(_TRANSIENT_BACKOFF_S)
                continue

            if response.status_code in {400, 401}:
                # Auth / input errors are permanent — fail fast with the API's message.
                raise PledgeQueueError(
                    f"{method} {path} -> {response.status_code}: {response.text}"
                )
            if response.status_code == 503 and attempt < _TRANSIENT_RETRIES:
                # Index rebuild right after a service restart — retry.
                self._sleep(_TRANSIENT_BACKOFF_S)
                continue

            response.raise_for_status()
            return response.json()

        raise PledgeQueueError(
            f"{method} {path} failed after {_TRANSIENT_RETRIES} attempts: {last_exc}"
        )
