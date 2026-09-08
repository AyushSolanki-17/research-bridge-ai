"""Evidence and attribution domain values.

Evidence identity is stable and does not include observation time.
Observation time is recorded but never changes the stable identifier.

Identity semantics:
  - Paper record: ``openalex:work:<work-id>`` where ``<work-id>`` is the
    normalized OpenAlex work ID (e.g., ``W2741809807``).
  - Citation assertion: ``openalex:citation:<citing-id>:<referenced-id>``
    (reserved for citation graph, same stability rule).

Two evidence records with the same stable ``id`` but different
``observed_at`` values refer to the same logical assertion observed at
different times.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import UTC, datetime


class InferenceStatus(enum.StrEnum):
    """Whether a value was reported or inferred.

    Attributes:
        REPORTED: Directly reported fact (e.g., title, citation count).
        INFERRED_PROVIDER: Value inferred or classified by the provider
            (e.g., OpenAlex topics with a supplied score).
    """

    REPORTED = "reported"
    INFERRED_PROVIDER = "inferred_provider"


@dataclass(frozen=True, slots=True)
class Evidence:
    """Stable, source-attributed evidence record.

    Attributes:
        id: Stable identifier, e.g., ``openalex:work:W2741809807``.
        provider: Provider name, e.g., ``openalex``.
        provider_record_id: Provider's record identifier, e.g., ``W2741809807``.
        source_url: Inspectable source reference URL.
        observed_at: Time the record was observed. Does not affect identity.
        inference_status: How the associated fact should be interpreted.
    """

    id: str
    provider: str
    provider_record_id: str
    source_url: str
    observed_at: datetime
    inference_status: InferenceStatus = InferenceStatus.REPORTED

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("evidence id must not be empty")
        if not self.provider:
            raise ValueError("provider must not be empty")
        if not self.provider_record_id:
            raise ValueError("provider_record_id must not be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")

    @staticmethod
    def paper_evidence(
        work_id: str,
        *,
        observed_at: datetime | None = None,
        source_url: str | None = None,
    ) -> Evidence:
        """Create evidence for an OpenAlex work record.

        Args:
            work_id: Normalized OpenAlex work ID (e.g., ``W2741809807``).
            observed_at: Observation time; defaults to now in UTC.
            source_url: Source URL; defaults to ``https://openalex.org/<id>``.

        Returns:
            Stable :class:`Evidence` with id ``openalex:work:<work-id>``.
        """
        normalized = work_id.upper()
        stable_id = f"openalex:work:{normalized}"
        url = source_url or f"https://openalex.org/{normalized}"
        ts = observed_at or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return Evidence(
            id=stable_id,
            provider="openalex",
            provider_record_id=normalized,
            source_url=url,
            observed_at=ts,
            inference_status=InferenceStatus.REPORTED,
        )

    @staticmethod
    def citation_evidence(
        citing_id: str,
        referenced_id: str,
        *,
        observed_at: datetime | None = None,
    ) -> Evidence:
        """Create evidence for a citation assertion.

        Args:
            citing_id: Normalized citing work ID.
            referenced_id: Normalized referenced work ID.
            observed_at: Observation time; defaults to now in UTC.

        Returns:
            Stable :class:`Evidence` with
            id ``openalex:citation:<citing>:<referenced>``.
        """
        c = citing_id.upper()
        r = referenced_id.upper()
        stable_id = f"openalex:citation:{c}:{r}"
        ts = observed_at or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return Evidence(
            id=stable_id,
            provider="openalex",
            provider_record_id=c,
            source_url=f"https://openalex.org/{c}",
            observed_at=ts,
            inference_status=InferenceStatus.REPORTED,
        )

    def to_dict(self) -> dict[str, str]:
        """Serialize to a JSON-compatible dict."""
        return {
            "id": self.id,
            "provider": self.provider,
            "provider_record_id": self.provider_record_id,
            "source_url": self.source_url,
            "observed_at": self.observed_at.isoformat(),
            "inference_status": self.inference_status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Evidence:
        """Deserialize from :meth:`to_dict` output.

        Args:
            data: Dict produced by :meth:`to_dict`.

        Returns:
            Reconstructed :class:`Evidence`.
        """
        return cls(
            id=data["id"],
            provider=data["provider"],
            provider_record_id=data["provider_record_id"],
            source_url=data["source_url"],
            observed_at=datetime.fromisoformat(data["observed_at"]),
            inference_status=InferenceStatus(data["inference_status"]),
        )
