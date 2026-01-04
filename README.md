# openai-agent

ChatKit-powered agent workspace with E2B Desktop (VNC) and Python sandboxes.

## Prerequisites

- Node.js 20+
- pnpm
- Python 3.10+ (for the custom ChatKit API server)
- Redis (local or managed)
- OpenAI API key + ChatKit workflow ID (hosted mode) or ChatKit API URL (custom)
- E2B API key

## Setup

```bash
pnpm install
```

Copy env file:

```bash
cp apps/web/.env.example apps/web/.env.local
```

If you use a custom OpenAI endpoint, set `OPENAI_BASE_URL` (include the `/v1` path).

Custom ChatKit API mode (recommended for `/v1/responses` backends):

1. Set the custom API vars in `apps/web/.env.local`:
   - `NEXT_PUBLIC_CHATKIT_API_URL=http://localhost:8000/chatkit`
   - `NEXT_PUBLIC_CHATKIT_DOMAIN_KEY=local-dev`
   - `NEXT_PUBLIC_CHATKIT_UPLOAD_URL=http://localhost:8000/files`
2. Start the Python ChatKit server:

```bash
make chatkit-install
make chatkit-dev
```

Hosted ChatKit mode:

- Keep `NEXT_PUBLIC_CHATKIT_WORKFLOW_ID` set and leave `NEXT_PUBLIC_CHATKIT_API_URL` unset.

Start Redis + Jaeger locally:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Jaeger UI: `http://localhost:16686`

Run the app:

```bash
pnpm dev
```

Visit `http://localhost:3000/workspace`.

## ChatKit server configuration

The custom ChatKit server reads these env vars (set in your shell or a `.env` file):

- `OPENAI_API_KEY` (required)
- `OPENAI_BASE_URL` (optional, include `/v1`)
- `OPENAI_AGENTS_DISABLE_TRACING` (optional, set `true` to disable agent tracing)
- `CHATKIT_MODEL` (default: `gpt-4.1-mini`)
- `CHATKIT_INSTRUCTIONS` (optional system prompt)
- `CHATKIT_PUBLIC_BASE_URL` (optional, defaults to request base URL)
- `CHATKIT_ALLOWED_ORIGINS` (comma-separated, default: `http://localhost:3000`)
- `CHATKIT_UPLOAD_DIR` (optional, defaults to `services/chatkit/uploads`)
- `CHATKIT_TRACE_MODE` (`openai` | `otel` | `none`, default: `openai`)
- `CHATKIT_TRACE_INCLUDE_DATA` (optional, include span data payloads in tracing)
- `CHATKIT_TOOL_OUTPUT_MODE` (`auto` | `function` | `text`, default: `auto`)
- `OTEL_EXPORTER_OTLP_ENDPOINT` (optional, OTLP/gRPC endpoint like `localhost:4317` or `http://localhost:4317`)
- `OTEL_EXPORTER_OTLP_INSECURE` (optional, set `true` for local collectors)
- `OTEL_SERVICE_NAME` (optional, default: `openai-agent-chatkit`)

To use Jaeger (OTLP/gRPC), set `CHATKIT_TRACE_MODE=otel` and keep
`OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317` (or `http://localhost:4317`).

## Project structure

- `apps/web`: Next.js app (UI + API routes)
- `apps/web/app/api`: ChatKit session + E2B sandbox endpoints
- `apps/web/components`: ChatKit + workspace panels
- `apps/web/lib`: Config, OpenAI client, E2B wrappers, Redis helpers
- `infra/docker-compose.yml`: Redis for local dev

## Notes

- ChatKit sessions are created server-side and refreshed automatically.
- E2B sandboxes are bound to ChatKit thread IDs with Redis TTL (30 minutes).
- Desktop stream URLs are returned only to the current user.
