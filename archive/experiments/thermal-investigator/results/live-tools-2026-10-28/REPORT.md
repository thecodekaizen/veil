# Live Meta tool integration

Two actual Muse Spark 1.3 calls, no automatic retries. Both provider responses completed; local semantic validation rejected both before tool or experiment execution.

1. Original flat contract: proposed `left-stair` but also populated `family=quadratic_loss`. The family is irrelevant to an experiment proposal, so it was rejected.
2. Manually amended nested operation schema: proposed `both-release` as confirmation of original model v1. Confirmation requires an already registered revision, so it was rejected.

The second schema corrected the first problem. It still allowed a model/kind relationship that the local validator forbids. The subsequent local patch now offers confirmation branches only for registered revisions; no third call was made. Both raw failures are retained. The legacy failed result.json describes attempt one; this report and summary.json describe the complete two-attempt run.

Actual reported tokens: 14169 input, 1223 output. Rate-based estimated cost: $0.022909. This is not an account billing balance. Local guard was $0.25, call cap two, synthetic public simulation evidence only.

This establishes API connectivity and rejection of invalid decisions. It does not establish a successful tool decision, model diagnosis, investigator advantage or hackathon readiness. The final schema fix has local tests only and still needs live verification in a separately bounded run.

Sources checked: https://dev.meta.ai/docs/pricing-rate-limits and https://dev.meta.ai/docs/structured-output . Nested operation branches avoid relying on prose to enforce field relationships.
