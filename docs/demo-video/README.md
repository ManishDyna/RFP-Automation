# SmartRFP — Marketing Demo Video

A single, self-contained product film + live tour for the Bahra Electric RFP
Automation System, built for marketing / sales showcase.

Three finished videos:

- **`SmartRFP-Promo-30s.mp4`** — punchy 30-second SaaS promo (1920×1080, light theme,
  deep-blue + cyan accent). Best for ads / landing page / social. Source: `promo.html`.
- **`SmartRFP-Features.mp4`** — full feature walkthrough (1920×1080, ~4:50, dark theme).
  Opens with the whole-system problem, then for **each** of nine features: a cinematic
  "the manual way → with SmartRFP" lead card, followed by the **real product** screen with
  animated inputs (e.g. select company), the button click, and the result. Source: `features.html`.
- **`SmartRFP-Final.mp4`** — full product film + live tour (1920×1080, ~10.5 min,
  cinematic dark theme). Best for sales demos. Source: `index.html`.

Open either `*.html` in a browser to play/scrub interactively, or re-render to MP4
with the script below.

## The 30-second promo (`promo.html`)

Storyboard, mapped to SmartRFP's real features & screens:

1. **Problem (0–5s)** — cluttered docs, many tabs, ticking deadline · "RFPs shouldn't take all week."
2. **Reveal (5–9s)** — clutter clears, the real Dashboard glides in, logo animates · "One portal. The whole RFP pipeline."
3. **Features (9–24s)** — real UI, smooth zoom, kinetic captions:
   1. RFP Insights — "Finds the right RFPs — automatically."
   2. Material Matching — "Matches every BOQ line to your materials."
   3. Open RFP & Reminders — "Routes to bidders. Guards every deadline."
   4. Submit (with cursor click) — "Submit back to the portal — in one click."
4. **Result (24–28s)** — "Submitted, with time to spare." · animated stats (70% faster, 2× more bids, 0 missed).
5. **Close (28–30s)** — logo lockup · tagline "From RFP to quote — automated." · CTA "Start automating today."

Edit tagline / captions / stats / feature screens in `promo.html` (top of the `<script>`:
`S` timeline, the `<Feature .../>` rows in `Movie`, and `SceneClose`).

## The full feature walkthrough (`features.html`)

Structure: **Intro → whole-system Problem → (cinematic "manual way" lead → real demo) × 9 → Outro.**
Every feature first shows the manual pain (cinematic, `sc-lead.jsx` `FeatLead`), then the
real product. The real demos animate the **inputs** too — Download highlights "Select
company", Submit highlights Open-RFP + Upload, Decline highlights Select-RFP, Schedule
highlights Frequency + Time zone — before the action click.

Nine features, end to end — each with an animated button click and a
step-by-step "what happens" explanation:

1. **Discover & Download** — click *Sync Portals* → live log (login → scrape → download BOQ → SharePoint → Dataverse).
2. **Material Matching** — two-tier logic (exact SAP code → keyword fallback) with confidence scores.
3. **Database & SharePoint** — records to Dataverse (OData) + files to SharePoint under the real tree `ALLRFPs/<Company>/<RFP>/download-file`, `TDS-files`, `Pricing-file`, `upload-rfp-file`.
4. **Actionable Email** — the real Bahra cards: set Result/Remark, attach file → written to Dataverse; team 3/5 status + Refresh.
5. **Deadline Reminders** — 3-day / 1-day timeline + the real URGENT notice; zero missed.
6. **Submit Response** — upload priced Excel + PDFs, click *Submit* → SharePoint TDS → portal post → status Submitted.
7. **Decline Participation** — pick a reason, click *Decline* → posted, recorded, removed from the open board.
8. **Schedule Automation** — set frequency/timezone/time, toggle on → unattended cron, Sun–Thu mornings.
9. **Analytics & Insights** — win rate, cycle time, volume by customer, outcomes; material insights.

**Download, Submit, Decline, Schedule and Analytics use the real product screenshots**
(in the dark browser frame) with a smooth cursor that clicks the actual button — then
shows the result: Download cross-fades to the real Activity Log; Submit/Decline/Schedule
pop a confirmation toast. The real-screenshot demo engine is `sc-demo.jsx` (`DemoShot`);
button coordinates are tuned to each screen. Email, Material Matching and the Dataverse +
SharePoint "source of truth" scenes are the illustrated explainers (`sc-emails.jsx`,
`sc-ingest.jsx`/`SceneMatch`, `sc-process.jsx`/`SceneStorage`). Sequence & narration: `features.html`.

> To re-aim a click after a UI change, run the sampler with `--calib` to overlay a
> coordinate grid + the current hotspot marker, read the button's stage X/Y, and update
> the `hotspot={{x,y}}` in `features.html`.

## What's in it

**Part 1 — The Story (cinematic, ~7.5 min)** — illustrated, narrated arc:

1. Title · 2. The Problem · 3. Flow Overview · 4. Discover & Ingest · 5. Auto-Match ·
6. Login & Dashboard · 7. RFP Insights · 8. **Actionable Email** (your 3 real Bahra
templates, recreated & animated) · 9. Open RFP & Reminders (real URGENT reminder) ·
10. Analytics · 11. Admin & Governance · 12. Business Value.

Real product screenshots are picture-in-pictured into the Dashboard, Auto-Match and
Analytics scenes as "LIVE PRODUCT" proof.

**Part 2 — The Live Product Tour (~3 min)** — 18 real portal screenshots with
Ken-Burns motion, covering every screen: sign-in, dashboard, download/schedule,
activity logs, material matching, RFP & material insights, open-RFP/remind/delegate,
submit/decline, analytics, users/roles, master data, audit trail, system settings.

On-screen captions double as the **voiceover script** — record VO over the MP4 to
narrate it, or present live. The full script is in `SmartRFP-Demo-Script.md`.

## Re-rendering the MP4

Uses the project venv (Playwright + Chromium) and a bundled ffmpeg
(`imageio-ffmpeg`, installed once via `pip install imageio-ffmpeg`).

```powershell
# 30-second promo → native 1080p (~1 min wall-clock):
env\Scripts\python.exe docs\demo-video\render.py --video --page promo.html --width 1920 --height 1080 --fps 30 --out SmartRFP-Promo-30s.mp4

# Full feature walkthrough (~4 min playback):
env\Scripts\python.exe docs\demo-video\render.py --video --page features.html --width 1280 --height 720 --fps 30 --out SmartRFP-Features.mp4

# Full film+tour — real-time capture (~12 min wall-clock):
env\Scripts\python.exe docs\demo-video\render.py --video --out SmartRFP-Final.mp4 --fps 30

# Deterministic — exact frame-by-frame (crisper, but slow: ~hours at this resolution):
env\Scripts\python.exe docs\demo-video\render.py --out SmartRFP-Final.mp4 --fps 24 --scale 1.5

# Preview stills for QA (writes docs/demo-video/samples/*.png):
env\Scripts\python.exe docs\demo-video\render.py --sample
```

## Editing content

- **Scenes / timing / narration**: `index.html` (`FILM`, `TOUR_STEPS`, `NARRATION`).
- **Email templates**: `sc-emails.jsx` (new-RFP card, team-status, urgent reminder).
- **Tour engine** (screenshots, Ken-Burns, callouts): `sc-tour.jsx`.
- **Illustrated film scenes**: `sc-*.jsx`. Shared kit/tokens: `smartrfp-kit.jsx`,
  `animations.jsx`.
- **Screenshots**: `assets/shots/` (copied from `docs/Application-ScreenShot/`).

> Note: the 3 email screens are faithful **recreations** of the real templates
> (crisper and animatable than embedding screenshots). To embed the literal PNGs
> instead, drop them in `assets/shots/` and swap the components in `sc-emails.jsx`.
