from lolcoach.analysis.build import finding_outcomes_for_ledger
from lolcoach.detectors.base import DetectorResult, Evidence, Finding, Phase, Severity
from lolcoach.detectors.gold_curve_shape import GoldCurveShapeDetector
from lolcoach.detectors.time_dead import TimeDeadDetector
from lolcoach.detectors.unspent_gold import UnspentGoldDetector
from lolcoach.detectors.ward_drought import WardDroughtDetector


def _finding(detector_id: str) -> Finding:
    return Finding(
        id=f"{detector_id}_1",
        detector_id=detector_id,
        detector_version=1,
        severity=Severity.MINOR,
        phase=Phase.EARLY,
        confidence=0.8,
        timestamps_s=(120.0,),
        evidence=(Evidence(key="e", label="e", value=1.0, unit="count"),),
    )


def test_finding_outcomes_for_ledger_excludes_not_applicable_and_error() -> None:
    results = [
        DetectorResult.with_findings(UnspentGoldDetector, (_finding(UnspentGoldDetector.id),)),
        DetectorResult.clean(WardDroughtDetector),
        DetectorResult.na(TimeDeadDetector, "ARAM has no lane opponent"),
        DetectorResult.error(GoldCurveShapeDetector, "boom"),
        DetectorResult.insufficient(TimeDeadDetector, "timeline too short"),
    ]

    assert finding_outcomes_for_ledger(results) == [
        (UnspentGoldDetector.id, "FINDINGS"),
        (WardDroughtDetector.id, "CLEAN"),
    ]


def test_finding_outcomes_for_ledger_empty_when_nothing_applicable() -> None:
    results = [DetectorResult.na(TimeDeadDetector, "no lane opponent")]
    assert finding_outcomes_for_ledger(results) == []
