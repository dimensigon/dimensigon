# Training Data Feedback Loop

- **Priority:** 20
- **Category:** AI
- **Effort:** 4-5 days
- **Dependencies:** #17 (Context-Aware AI in WebManager)

## Context

The AI model improves with better training data. Currently, training examples are static.
When operators use AI to create orchestrations that work well in production, those successful
orchestrations are valuable training signals that are lost. A feedback loop automatically
captures successful AI-generated orchestrations, validates them, and incorporates them into
the training set for continuous improvement.

## Scope

- Auto-capture: when an AI-generated orchestration executes successfully N times (configurable,
  default 3), flag it as a training candidate.
- Quality validation: ensure the captured orchestration meets quality criteria (has error
  handling, reasonable timeouts, uses variables not hardcoded values).
- Human review gate: flagged candidates appear in a review queue for admin approval.
- Training pipeline: approved examples are formatted and added to the training dataset.
- Periodic retraining: scheduled job to retrain/fine-tune the model with new data.
- Metrics: track training set growth, model improvement (response quality scores).

## Files to Modify

- `dimensigon/ai/feedback.py` (new: capture, validate, queue, retrain pipeline)
- `dimensigon/ai/handler.py` (tag AI-generated orchestrations for tracking)
- `scripts/training/retrain.py` (new: retraining script)
- `dimensigon/domain/entities/training_candidate.py` (new: candidate model)
- `dimensigon/web/admin/routes.py` (review queue UI routes)
- `templates/admin/dashboard.html` (review queue panel)
- DB migration for training_candidate table.

## Implementation Steps

1. Define `TrainingCandidate` entity: id, orchestration_id, source (ai_generated), success_count,
   quality_score, status (pending|approved|rejected), reviewer, reviewed_at.
2. Create DB migration.
3. Tag AI-generated orchestrations in handler.py with `source=ai_generated` metadata.
4. After each successful execution, increment success_count. At threshold, set status=pending.
5. Build quality validator: check for error handling, timeout configuration, variable usage,
   step count, and documentation.
6. Build review queue UI: list of candidates with quality score, orchestration preview,
   approve/reject buttons.
7. On approval: format the orchestration as a training example and append to the training set.
8. Build retraining script: loads current training set, adds new examples, runs fine-tuning.
9. Schedule retraining as a weekly cron job (or trigger manually from dashboard).
10. Track metrics: training set size over time, average quality score trend.

## Verification

- AI creates an orchestration, it runs successfully 3 times: appears in review queue.
- Quality score reflects presence/absence of best practices.
- Admin approves: example is added to training dataset (file or DB).
- Retraining script runs without errors and produces an updated model checkpoint.

## Breaking Changes

- None. The feedback loop is passive; it observes existing behavior without altering it.
- Retraining requires compute resources and must be scheduled during off-peak hours.
