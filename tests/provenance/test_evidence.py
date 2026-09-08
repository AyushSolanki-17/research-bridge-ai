"""Evidence identity and serialization tests."""

from datetime import UTC, datetime

from research_bridge.provenance.domain.evidence import Evidence, InferenceStatus


def test_paper_evidence_identity_stable_across_observation_time() -> None:
    t1 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 8, 0, 0, tzinfo=UTC)
    e1 = Evidence.paper_evidence("W2741809807", observed_at=t1)
    e2 = Evidence.paper_evidence("W2741809807", observed_at=t2)
    assert e1.id == "openalex:work:W2741809807"
    assert e1.id == e2.id
    assert e1.provider == "openalex"
    assert e1.provider_record_id == "W2741809807"
    assert e1.source_url == "https://openalex.org/W2741809807"
    assert e2.source_url == e1.source_url
    assert e1.observed_at != e2.observed_at
    # Identity does not include observation time.
    assert e1.id == e2.id


def test_citation_evidence_identity() -> None:
    e = Evidence.citation_evidence("W1", "W2")
    assert e.id == "openalex:citation:W1:W2"


def test_evidence_serialization_round_trip() -> None:
    ts = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    original = Evidence(
        id="openalex:work:W2741809807",
        provider="openalex",
        provider_record_id="W2741809807",
        source_url="https://openalex.org/W2741809807",
        observed_at=ts,
        inference_status=InferenceStatus.REPORTED,
    )
    data = original.to_dict()
    restored = Evidence.from_dict(data)
    assert restored == original
    # Distinct observation time still round-trips correctly.
    data2 = original.to_dict()
    data2["observed_at"] = ts.isoformat()
    assert Evidence.from_dict(data2).observed_at == ts


def test_evidence_requires_timezone_aware() -> None:
    import pytest

    naive = datetime(2026, 1, 1, 12, 0)
    with pytest.raises(ValueError):
        Evidence(
            id="openalex:work:W1",
            provider="openalex",
            provider_record_id="W1",
            source_url="https://openalex.org/W1",
            observed_at=naive,
        )
