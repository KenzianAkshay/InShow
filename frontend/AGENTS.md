# Frontend conventions

The Next.js frontend is added in Part 3. This document records the conventions
later parts must follow.

## Stack

- Next.js (App Router), running as `next start` in its own container.
- Talks to the backend only through `/api` (FastAPI). No direct database access.

## Theme

Enterprise theme. Define the color scheme once as CSS variables / design tokens
and reference them everywhere. Do not hardcode hex values in components.

- Coral `#FF7A59` - primary CTA, key actions, brand accent
- Pickled Bluewood `#33475B` - headings, nav background, logo
- Deep Bluewood `#2D3E50` - sidebar, dark surfaces
- Cerulean `#0091AE` - links, interactive elements, info
- Jade `#00BDA5` - success, positive indicators
- Marigold `#F5C26B` - warnings, alerts
- Watermelon `#F2545B` - errors, danger
- Slate `#516F90` - muted/secondary text
- Heather `#7C98B6` - placeholder, inactive
- Fog `#EAF0F6` - page backgrounds, table rows
- Geyser `#DFE3EB` - borders, dividers
- Forget Me Not `#FFF1EE` - coral tint backgrounds, empty states

## Structure

- Reusable components under `components/`.
- API access wrapped in a small client module; no scattered `fetch` calls.
- Auth state drives route guards (redirect to `/login` when unauthenticated).

## Standards

- Latest idiomatic library versions.
- Keep it simple; no over-engineering; no unnecessary defensive code.
- No emojis. Minimal README.
- Root-cause issues before fixing; prove with evidence.
