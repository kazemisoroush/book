# Frontend

The Studio UI. A Next.js static-export app that is the studio's face for parsing, casting, and producing a book. It holds no business logic; its only link to the backend is the typed API client.

## Contract

The client is generated from the repo-root `openapi.yaml`, which is exported from the FastAPI app. Regenerate it with `npm run generate:api`; CI fails if it drifts from the contract.

## Layout

- `app/` routes and the design system (`globals.css`, `layout.tsx`).
- `components/` presentational components, no data access.
- `lib/api/` the generated schema and the typed client.
- `lib/config.ts` where the API base URL comes from.
- `lib/books.ts` the book data-access and display helpers.

## Design

A casting room for a 19th-century Russian gambling drama: a dark baize-black ground, warm aged-paper type, one crimson accent, gilt used sparingly, Fraunces paired with Archivo.

## Run

`make web-dev` from the repo root, or `npm run dev` here, serves the UI on port 3000. It reads the API from `NEXT_PUBLIC_API_URL`, defaulting to the local FastAPI. Start the API with `make serve`.

## Build and test

`npm run build` emits the static site into `out/`. `npm run test` runs the vitest suite; `npm run typecheck` and `npm run lint` run the type and lint checks.
