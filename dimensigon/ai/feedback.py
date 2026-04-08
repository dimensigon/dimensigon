"""Training data feedback loop for AI-generated orchestrations.

Tracks successful executions of AI-generated orchestrations, computes quality
scores, and provides a review queue for human approval before promoting
orchestrations to training data.
"""
import logging

from sqlalchemy import select

from dimensigon.utils.helpers import get_now
from dimensigon.web import db

_LOGGER = logging.getLogger('dm.ai.feedback')

# Number of successful executions before a candidate is promoted to 'pending'
SUCCESS_THRESHOLD = 3


def increment_success(orchestration_id):
    """Increment the success_count for the matching training candidate.

    When the count reaches SUCCESS_THRESHOLD the candidate status is promoted
    from 'tracking' to 'pending' (ready for human review).

    Returns the updated TrainingCandidate or None if not found.
    """
    from dimensigon.domain.entities.training_candidate import TrainingCandidate

    candidate = db.session.execute(
        select(TrainingCandidate).filter_by(
            orchestration_id=str(orchestration_id),
            status='tracking',
        )
    ).scalars().first()

    if candidate is None:
        return None

    candidate.success_count = (candidate.success_count or 0) + 1

    if candidate.success_count >= SUCCESS_THRESHOLD:
        candidate.status = 'pending'
        _LOGGER.info(
            'Training candidate %s promoted to pending (success_count=%d)',
            candidate.id, candidate.success_count,
        )

    db.session.commit()
    return candidate


def compute_quality_score(orchestration_json):
    """Compute a quality score (0.0 - 1.0) for an orchestration JSON.

    Scoring criteria (each worth 0.2):
      - has_error_handling: steps reference error handling or undo logic
      - has_timeouts: timeout values are specified
      - uses_variables: uses {{variable}} placeholders rather than hardcoded values
      - has_description: orchestration has a non-empty description
      - reasonable_step_count: between 1 and 20 steps (inclusive)
    """
    if not orchestration_json or not isinstance(orchestration_json, dict):
        return 0.0

    score = 0.0
    json_str = str(orchestration_json).lower()

    # 1. Has error handling (undo_on_error, stop_on_error, try/catch patterns)
    if any(kw in json_str for kw in ('undo_on_error', 'stop_on_error', 'error_handl', 'on_error', 'rescue')):
        score += 0.2

    # 2. Has timeouts
    if any(kw in json_str for kw in ('timeout', 'time_out', 'max_time', 'deadline')):
        score += 0.2

    # 3. Uses variables ({{...}} patterns) rather than only hardcoded values
    if '{{' in json_str and '}}' in json_str:
        score += 0.2

    # 4. Has a non-empty description
    description = orchestration_json.get('description', '')
    if description and isinstance(description, str) and len(description.strip()) > 0:
        score += 0.2

    # 5. Reasonable step count (1-20)
    steps = orchestration_json.get('steps', [])
    if isinstance(steps, list) and 1 <= len(steps) <= 20:
        score += 0.2

    return round(score, 2)


def get_review_queue():
    """Return a list of pending training candidates with orchestration details.

    Returns list of dicts with candidate info and orchestration name.
    """
    from dimensigon.domain.entities.training_candidate import TrainingCandidate

    candidates = db.session.execute(
        select(TrainingCandidate)
        .filter_by(status='pending')
        .order_by(TrainingCandidate.created_at.desc())
    ).scalars().all()

    result = []
    for c in candidates:
        entry = c.to_json()
        entry['orchestration_name'] = c.orchestration.name if c.orchestration else None
        result.append(entry)

    return result


def approve_candidate(candidate_id, reviewer):
    """Approve a training candidate: set status to 'approved' and record reviewer.

    Returns the updated TrainingCandidate or None if not found / not pending.
    """
    from dimensigon.domain.entities.training_candidate import TrainingCandidate

    candidate = db.session.get(TrainingCandidate, str(candidate_id))
    if candidate is None or candidate.status != 'pending':
        return None

    candidate.status = 'approved'
    candidate.reviewer = reviewer
    candidate.reviewed_at = get_now()
    db.session.commit()

    _LOGGER.info('Training candidate %s approved by %s', candidate.id, reviewer)
    return candidate


def reject_candidate(candidate_id, reviewer):
    """Reject a training candidate: set status to 'rejected' and record reviewer.

    Returns the updated TrainingCandidate or None if not found / not pending.
    """
    from dimensigon.domain.entities.training_candidate import TrainingCandidate

    candidate = db.session.get(TrainingCandidate, str(candidate_id))
    if candidate is None or candidate.status != 'pending':
        return None

    candidate.status = 'rejected'
    candidate.reviewer = reviewer
    candidate.reviewed_at = get_now()
    db.session.commit()

    _LOGGER.info('Training candidate %s rejected by %s', candidate.id, reviewer)
    return candidate
