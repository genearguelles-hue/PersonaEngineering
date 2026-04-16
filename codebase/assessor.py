from dataclasses import dataclass

from ledger_store import LedgerStore


@dataclass
class AssessmentReport:
    ledger_valid: bool
    total_entries: int

    max_axiom_pressure: int
    max_primitive_saturation: int

    first_axiom_pressure: int
    last_axiom_pressure: int
    pressure_delta: int
    pressure_trend: str

    first_primitive_saturation: int
    last_primitive_saturation: int
    saturation_delta: int
    saturation_trend: str

    drift_warnings: int
    stable_entries: int

    near_threshold_pressure_count: int
    near_threshold_saturation_count: int

    trajectory_status: str
    persona_valid: bool
    summary: str


class Assessor:
    def __init__(
        self,
        axiom_pressure_threshold: int = 3,
        primitive_saturation_threshold: int = 3
    ) -> None:
        self.axiom_pressure_threshold = axiom_pressure_threshold
        self.primitive_saturation_threshold = primitive_saturation_threshold

    def _classify_trend(self, delta: int) -> str:
        if delta < 0:
            return "improving"
        if delta > 0:
            return "worsening"
        return "stable"

    def _classify_trajectory_status(
        self,
        pressure_trend: str,
        saturation_trend: str,
        near_threshold_pressure_count: int,
        near_threshold_saturation_count: int,
        drift_warnings: int
    ) -> str:
        if drift_warnings > 0:
            return "degrading"

        if pressure_trend == "worsening" or saturation_trend == "worsening":
            return "degrading"

        if near_threshold_pressure_count > 1 or near_threshold_saturation_count > 1:
            return "at-risk"

        if pressure_trend == "improving" or saturation_trend == "improving":
            return "stabilizing"

        return "stable"

    def assess(self, ledger_path: str) -> AssessmentReport:
        ledger = LedgerStore.load(ledger_path)
        entries = ledger.entries()

        ledger_valid = ledger.verify()
        total_entries = len(entries)

        if total_entries == 0:
            return AssessmentReport(
                ledger_valid=ledger_valid,
                total_entries=0,
                max_axiom_pressure=0,
                max_primitive_saturation=0,
                first_axiom_pressure=0,
                last_axiom_pressure=0,
                pressure_delta=0,
                pressure_trend="stable",
                first_primitive_saturation=0,
                last_primitive_saturation=0,
                saturation_delta=0,
                saturation_trend="stable",
                drift_warnings=0,
                stable_entries=0,
                near_threshold_pressure_count=0,
                near_threshold_saturation_count=0,
                trajectory_status="stable",
                persona_valid=ledger_valid,
                summary="Ledger is empty. No persona trajectory to assess."
            )

        max_axiom_pressure = max(entry.axiom_pressure for entry in entries)
        max_primitive_saturation = max(entry.primitive_saturation for entry in entries)

        first_axiom_pressure = entries[0].axiom_pressure
        last_axiom_pressure = entries[-1].axiom_pressure
        pressure_delta = last_axiom_pressure - first_axiom_pressure
        pressure_trend = self._classify_trend(pressure_delta)

        first_primitive_saturation = entries[0].primitive_saturation
        last_primitive_saturation = entries[-1].primitive_saturation
        saturation_delta = last_primitive_saturation - first_primitive_saturation
        saturation_trend = self._classify_trend(saturation_delta)

        drift_warnings = sum(1 for entry in entries if "⚠️" in entry.drift_status)
        stable_entries = sum(1 for entry in entries if "✅" in entry.drift_status)

        near_threshold_pressure_count = sum(
            1 for entry in entries
            if entry.axiom_pressure >= self.axiom_pressure_threshold - 1
        )

        near_threshold_saturation_count = sum(
            1 for entry in entries
            if entry.primitive_saturation >= self.primitive_saturation_threshold - 1
        )

        trajectory_status = self._classify_trajectory_status(
            pressure_trend=pressure_trend,
            saturation_trend=saturation_trend,
            near_threshold_pressure_count=near_threshold_pressure_count,
            near_threshold_saturation_count=near_threshold_saturation_count,
            drift_warnings=drift_warnings
        )

        persona_valid = (
            ledger_valid
            and max_axiom_pressure <= self.axiom_pressure_threshold
            and max_primitive_saturation <= self.primitive_saturation_threshold
            and trajectory_status in {"stable", "stabilizing", "at-risk"}
        )

        if not ledger_valid:
            summary = "Ledger integrity failure: hash chain is invalid."
        elif trajectory_status == "degrading":
            summary = (
                "Persona trajectory is degrading: pressure or saturation is worsening "
                "or drift warnings are present."
            )
        elif trajectory_status == "at-risk":
            summary = (
                "Persona remains valid but shows repeated near-threshold behavior."
            )
        elif trajectory_status == "stabilizing":
            summary = "Persona remains valid and the trajectory appears to be stabilizing."
        else:
            summary = "Persona remains within acceptable parameters and trajectory is stable."

        return AssessmentReport(
            ledger_valid=ledger_valid,
            total_entries=total_entries,
            max_axiom_pressure=max_axiom_pressure,
            max_primitive_saturation=max_primitive_saturation,
            first_axiom_pressure=first_axiom_pressure,
            last_axiom_pressure=last_axiom_pressure,
            pressure_delta=pressure_delta,
            pressure_trend=pressure_trend,
            first_primitive_saturation=first_primitive_saturation,
            last_primitive_saturation=last_primitive_saturation,
            saturation_delta=saturation_delta,
            saturation_trend=saturation_trend,
            drift_warnings=drift_warnings,
            stable_entries=stable_entries,
            near_threshold_pressure_count=near_threshold_pressure_count,
            near_threshold_saturation_count=near_threshold_saturation_count,
            trajectory_status=trajectory_status,
            persona_valid=persona_valid,
            summary=summary
        )