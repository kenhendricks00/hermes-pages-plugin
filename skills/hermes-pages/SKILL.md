---
name: hermes-pages
description: "Use when asked to render or publish an answer as a page."
version: "1.0.0"
license: MIT
---

# Hermes Pages

Make a readable page, not a wall of chat. Use this skill when a user asks for a rendered response, a page, or a shareable answer. A long answer alone is not permission to publish.

## Consent and boundaries

- Local rendering and public hosting are separate actions. Never upload without explicit publish intent. Warn that every managed page AND the index become public, not just the newest page. Public URLs are not access control.
- Never include credentials, account identifiers, private conversations, or sensitive documents without informed, specific authorization. A private Git repository does not make a hosted page private.
- Do not reuse a user's existing site, DNS or unrelated Pages project. Ask for a dedicated workspace and NEW project name. Do not install software globally or silently install anything.
- Use only the included standalone utility and ordinary user-approved terminal commands. No Hermes internals, auth-store reads, browser token extraction, background jobs or auto-updaters.

## Local workflow

Resolve `scripts/hermes_pages.py` relative to this installed skill directory. Quote paths and use a subprocess argument list, never concatenate user text into shell commands. Python 3.10+ is required; the renderer has no package dependencies.

1. Choose a dedicated output workspace. The CLI defaults to `$HERMES_HOME/hermes-pages`, falling back to `~/.hermes/hermes-pages`. Prefer an explicit `--workspace` for clarity. Do not change another profile.
2. `python <skill>/scripts/hermes_pages.py --workspace <workspace> setup`
3. Write approved content to a UTF-8 file outside the public directory.
4. `python <skill>/scripts/hermes_pages.py --workspace <workspace> render <input.md> --title "Title" --summary "One or two sentences" --slug useful-note`
5. Open the output locally and inspect it. Use `--wide` only for dashboards. Use `--replace` for an intentional existing managed-page update; exact repeats are idempotent. Never delete safety locks just to bypass an active process.

Markdown supports headings, one-line paragraphs, flat ordered/unordered lists, blockquotes, fenced code, basic links, bold, inline code and simple pipe tables. Raw HTML in Markdown is escaped. For cards and callouts, use `--html` with user-authorized HTML. HTML is trusted, NOT sanitized; never ingest untrusted remote HTML. Metadata is escaped and template substitution is single-pass. Default Cloudflare headers restrict scripts, embeds and outbound connections, but local file viewing has no HTTP CSP. Do not treat CSP as an HTML sanitizer.

## Explicit free hosting

1. Read `references/hosting.md` and run `guide` for user-facing steps.
2. Check for an existing Wrangler executable. If absent, offer a manual local install using Cloudflare's official instructions, or dashboard drag-and-drop. Never auto-run npx downloads or alter global credentials/settings.
3. User runs `wrangler login` in their interactive terminal, using Cloudflare's OAuth screen. Do not ask for chat tokens or inspect Wrangler's credential files. Do not launch browser OAuth in unattended/cron sessions.
4. User explicitly creates a NEW dedicated static project: `wrangler pages project create YOUR-NEW-PROJECT --production-branch main`. Do not choose an existing site or a paid resource.
5. Review all managed pages with the user. Run `publish --project YOUR-NEW-PROJECT --dry-run` first. Then, only on publish intent, run `publish --project YOUR-NEW-PROJECT --confirm-public` (add `--wrangler` with the existing executable path if needed).
6. The utility stages ONLY managed public assets, checks hashes, and calls Wrangler with an argument list, isolated cwd and 180-second timeout. It does not retrieve tokens. Wrangler owns its own OAuth and network behavior. No source files, unmanaged files or functions are uploaded.
7. Read the exact deployment URL from Wrangler output. Fetch it and verify the expected title/content and CSS/JS content types. Never invent a pages.dev URL or claim an unverified deployment succeeded. Return the actual URL and remind the user it is public.

## Page design

Use a descriptive title and short summary. One shared 700px content column, system fonts, neutral near-white or black paper, blue links, a quiet sticky action bar. Group related material in `.grid` / `.card`; use `.callout.info`, `.warning`, `.success` or `.danger` sparingly. Use `.num` for numeric cells. Avoid decorative noise. Readable on phones, printable with browser Save as PDF, with an optional Listen control. Speech depends on browser voices and may use the browser vendor's service. Do not promise offline speech.

## Verify and maintain

Run `python -m unittest discover -s tests -v` from the source repository after changes. Validate portable packaging with `hermes plugins validate <repo> --install-deps`. Updates go through reviewed commit pins, never self-update. See `references/hosting.md` for limits and `references/maintenance.md` for a reusable release checklist.
