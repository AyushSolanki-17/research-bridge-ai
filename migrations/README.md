# Migrations

Keep database migrations ordered at the repository root. Record the owning capability and coordinate cross-capability migration order here. Schema ownership remains with that capability; adapters live under its infrastructure layer. Add migration tooling with the first persisted schema, including compatibility, resumable backfill and recovery instructions.
