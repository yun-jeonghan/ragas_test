# Vendor Issues Log

This file tracks issues found in `vendor/benchmark-qed` and related vendored code.
Update this file whenever vendored code is inspected, patched, or found to behave unexpectedly.

## Format

- `Date`
- `Area`
- `Issue`
- `Impact`
- `Status`
- `Notes`

## 2026-06-03

- `Area`: `vendor/benchmark-qed/benchmark_qed/autoq/question_gen/data_questions/assertion_gen/*`
- `Issue`: Assertion generation emits `score` values like `85`, but the vendored `Assertion.score` model only accepts `1..10`.
- `Impact`: Assertions are created in raw LLM output, but object construction drops them, leaving `assertion_count=0` in smoke runs.
- `Status`: Fixed locally
- `Notes`: Added score normalization before Assertion construction in local/global assertion generation paths. Percentage-like scores are now mapped into the 1-10 range instead of being dropped.

## How to extend

When you touch vendored code:

1. Add a new dated entry here.
2. Note the exact file or module.
3. Describe the observed behavior and user-visible impact.
4. Mark whether it is open, mitigated, or fixed.
5. If the issue is fixed in a local patch, record the follow-up commit or code path.
