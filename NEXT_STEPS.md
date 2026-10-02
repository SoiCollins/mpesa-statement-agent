# Next steps for Collins

Make these changes yourself so you can explain the implementation and tradeoffs in an interview:

1. Add a transaction-category correction endpoint and tests, then make corrected categories affect later answers.
2. Add one authorized, sanitized statement-export format and parser fixtures for its date and amount edge cases.
3. Replace the in-memory repository with SQLite, migrations, and a test for persistence across app restarts.
4. Add per-business anomaly thresholds and an evaluation showing the precision/recall tradeoff on reviewed synthetic cases.
5. Add authentication, statement ownership checks, deletion/retention behavior, and a deployment with request/error monitoring.
