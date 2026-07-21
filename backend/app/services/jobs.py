import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError


JobType = Literal["voice", "video"]
JobStatus = Literal["queued", "processing", "completed", "failed"]
_STORE_LOCK = RLock()


class JobNotFoundError(LookupError):
    """Raised when a requested render job does not exist."""


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    job_type: JobType
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    result: dict[str, object] | None = None
    error: str | None = Field(default=None, max_length=500)


class JobSubmission(BaseModel):
    job_id: UUID
    job_type: JobType
    status: Literal["queued"] = "queued"
    status_url: str


class JobStore:
    """Small atomic JSON job store suitable for one GPU API process."""

    def __init__(self, directory: Path):
        self.directory = directory

    def create(self, job_type: JobType) -> JobRecord:
        now = datetime.now(UTC)
        record = JobRecord(
            job_id=uuid4(),
            job_type=job_type,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        self._write(record)
        return record

    def get(self, job_id: UUID) -> JobRecord:
        path = self._path(job_id)
        try:
            contents = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise JobNotFoundError("Job not found.") from exc

        try:
            return JobRecord.model_validate_json(contents)
        except ValidationError as exc:
            raise RuntimeError("Stored job metadata is invalid.") from exc

    def set_processing(self, job_id: UUID) -> JobRecord:
        return self._update(job_id, status="processing", result=None, error=None)

    def complete(self, job_id: UUID, result: dict[str, object]) -> JobRecord:
        return self._update(job_id, status="completed", result=result, error=None)

    def fail(self, job_id: UUID, error: str) -> JobRecord:
        return self._update(job_id, status="failed", result=None, error=error)

    def _update(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        result: dict[str, object] | None,
        error: str | None,
    ) -> JobRecord:
        with _STORE_LOCK:
            current = self.get(job_id)
            updated = current.model_copy(
                update={
                    "status": status,
                    "updated_at": datetime.now(UTC),
                    "result": result,
                    "error": error,
                }
            )
            self._write_unlocked(updated)
        return updated

    def _path(self, job_id: UUID) -> Path:
        return self.directory / f"{job_id}.json"

    def _write(self, record: JobRecord) -> None:
        with _STORE_LOCK:
            self._write_unlocked(record)

    def _write_unlocked(self, record: JobRecord) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self._path(record.job_id)
        temporary = self.directory / f".{record.job_id}.{uuid4()}.tmp"
        payload = json.dumps(
            record.model_dump(mode="json"),
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            temporary.write_text(payload, encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
