# ADR 0001: Framework-independent core and adapters

Status: accepted. Supersedes the capability-layer directory convention.

## Context

The original capability layout placed roughly three thousand lines of source behind
repeated `domain/application/infrastructure` paths. Library callers also had to know
internal use-case classes, while FastAPI and CLI duplicated their composition. A
logical responsibility does not require a layer directory or separate distribution.

## Decision

Keep one distribution under `src/`. Put framework-independent models, ports and
operations in focused modules under `research_bridge/core/`. Expose their supported
composition through `ResearchBridge`. Put concrete acquisition under `providers/`
and FastAPI integration under `api/`. API routers receive a configured façade and do
not use application state as a service locator. Only standalone entrypoints choose a
provider.

Reserve `packages/` for demonstrated standalone library extraction. Follow [architecture](../architecture.md) for repository-specific source paths and dependency rules.

## Consequences

Consumers get one short import path and one façade across Python, HTTP and CLI.
Developers navigate by responsibility without empty or repeated layer directories.
The core cannot depend on HTTP, FastAPI or provider implementations; executable
architecture checks enforce that boundary. OpenAlex remains the default adapter but
is not constructed inside business code or routers.
