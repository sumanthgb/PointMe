"""
workers/clinical_trials.py — Worker 2: ClinicalTrials.gov v2 API

API: https://clinicaltrials.gov/api/v2/studies
Fetches active, completed, and failed trials for a target-disease pair.
The 'whyStopped' field on failed/terminated trials is the key signal.
"""

import time
# httpx imported lazily inside functions (avoids import errors in test environments)
from models import ClinicalTrialsResult, Trial, WorkerMeta, WorkerStatus
from config import CLINICALTRIALS_MAX_RESULTS

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

# Trial statuses we consider "failed" / terminated
FAILED_STATUSES = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
COMPLETED_STATUSES = {"COMPLETED"}
ACTIVE_STATUSES = {"RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION",
                   "NOT_YET_RECRUITING", "AVAILABLE"}


def _parse_trial(study: dict) -> Trial:
    """Parse a ClinicalTrials.gov v2 study object into our Trial model."""
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    outcomes = proto.get("outcomesModule", {})

    phases = design.get("phases", [])
    phase_str = phases[0] if phases else None

    primary_outcomes = outcomes.get("primaryOutcomes", [])
    primary_outcome_str = primary_outcomes[0].get("measure") if primary_outcomes else None

    return Trial(
        nct_id=ident.get("nctId", ""),
        title=ident.get("briefTitle", ""),
        phase=phase_str,
        status=status.get("overallStatus", ""),
        why_stopped=status.get("whyStopped"),   # ← GOLD for failed trial analysis
        enrollment=design.get("enrollmentInfo", {}).get("count"),
        start_date=status.get("startDateStruct", {}).get("date"),
        primary_outcome=primary_outcome_str,
    )


def fetch_clinical_trials(target: str, disease: str) -> ClinicalTrialsResult:
    """
    Fetch clinical trials for a target-disease pair from ClinicalTrials.gov v2 API.

    Args:
        target:  e.g. "KRAS G12C" or "KRAS"
        disease: e.g. "non-small cell lung cancer"

    Returns:
        ClinicalTrialsResult with active, completed, and failed trial lists.
    """
    start = time.time()

    try:
        params = {
            "query.cond": disease,
            "query.intr": target,
            "pageSize": CLINICALTRIALS_MAX_RESULTS,
            "format": "json",
            # Return only the fields we care about
            "fields": (
                "NCTId,BriefTitle,OverallStatus,WhyStopped,"
                "Phase,EnrollmentCount,StartDate,PrimaryOutcomeMeasure"
            ),
        }

        import urllib.request
        import urllib.parse
        import json
        
        query_string = urllib.parse.urlencode(params)
        url = f"{BASE_URL}?{query_string}"
        
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

        studies = data.get("studies", [])

        active_trials    = []
        completed_trials = []
        failed_trials    = []
        phase_counts: dict[str, int] = {}

        for study in studies:
            trial = _parse_trial(study)
            status_upper = trial.status.upper()

            # Bucket by status
            if status_upper in FAILED_STATUSES:
                failed_trials.append(trial)
            elif status_upper in COMPLETED_STATUSES:
                completed_trials.append(trial)
            elif status_upper in ACTIVE_STATUSES:
                active_trials.append(trial)

            # Count phases
            if trial.phase:
                phase_counts[trial.phase] = phase_counts.get(trial.phase, 0) + 1

        # Success rate: completed / (completed + failed), avoid div-by-zero
        total_resolved = len(completed_trials) + len(failed_trials)
        success_rate = len(completed_trials) / total_resolved if total_resolved > 0 else 0.0

        elapsed = int((time.time() - start) * 1000)
        return ClinicalTrialsResult(
            active_trials=active_trials,
            completed_trials=completed_trials,
            failed_trials=failed_trials,
            phases=phase_counts,
            success_rate=success_rate,
            meta=WorkerMeta(status=WorkerStatus.SUCCESS, query_time_ms=elapsed)
        )

    except Exception as e:
        return ClinicalTrialsResult(
            meta=WorkerMeta(
                status=WorkerStatus.FAILED,
                query_time_ms=int((time.time() - start) * 1000),
                error=str(e)
            )
        )


def supplement_with_drug_names(
    ct_result: ClinicalTrialsResult,
    drug_names: list[str],
    disease: str,
) -> ClinicalTrialsResult:
    """
    Supplement an existing ClinicalTrialsResult by also searching each known drug name.

    Many targets (e.g. BACE1, CETP) have trials filed under drug trade/generic names
    rather than the gene symbol, so a gene-based search misses them entirely.
    This function deduplicates by NCT ID and recomputes the success rate.

    Args:
        ct_result:   Existing result from fetch_clinical_trials (gene-name search).
        drug_names:  Drug names to additionally search (from Open Targets knownDrugs).
        disease:     Disease string (same as the original query).

    Returns:
        Merged ClinicalTrialsResult with deduped trials and recomputed success_rate.
    """
    if not drug_names or ct_result.meta.status == WorkerStatus.FAILED:
        return ct_result

    import urllib.request
    import urllib.parse
    import json

    seen_ids: set[str] = {t.nct_id for t in (
        ct_result.active_trials + ct_result.completed_trials + ct_result.failed_trials
    )}

    active_extra:    list[Trial] = []
    completed_extra: list[Trial] = []
    failed_extra:    list[Trial] = []
    phase_counts = dict(ct_result.phases)

    try:
        for drug in drug_names[:10]:  # cap to avoid too many requests
            params = {
                "query.cond": disease,
                "query.intr": drug,
                "pageSize": 20,
                "format": "json",
                "fields": (
                    "NCTId,BriefTitle,OverallStatus,WhyStopped,"
                    "Phase,EnrollmentCount,StartDate,PrimaryOutcomeMeasure"
                ),
            }
            query_string = urllib.parse.urlencode(params)
            url = f"{BASE_URL}?{query_string}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode())
            except Exception:
                continue
                
            for study in data.get("studies", []):
                    trial = _parse_trial(study)
                    if trial.nct_id in seen_ids:
                        continue
                    seen_ids.add(trial.nct_id)
                    status_upper = trial.status.upper()
                    if status_upper in FAILED_STATUSES:
                        failed_extra.append(trial)
                    elif status_upper in COMPLETED_STATUSES:
                        completed_extra.append(trial)
                    elif status_upper in ACTIVE_STATUSES:
                        active_extra.append(trial)
                    if trial.phase:
                        phase_counts[trial.phase] = phase_counts.get(trial.phase, 0) + 1
    except Exception:
        # Supplementary step — silently ignore failures, return what we have
        pass

    merged_active    = ct_result.active_trials    + active_extra
    merged_completed = ct_result.completed_trials + completed_extra
    merged_failed    = ct_result.failed_trials    + failed_extra

    total_resolved = len(merged_completed) + len(merged_failed)
    success_rate = len(merged_completed) / total_resolved if total_resolved > 0 else 0.0

    return ClinicalTrialsResult(
        active_trials=merged_active,
        completed_trials=merged_completed,
        failed_trials=merged_failed,
        phases=phase_counts,
        success_rate=success_rate,
        meta=ct_result.meta,
    )
