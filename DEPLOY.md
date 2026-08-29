# SwingLens — Showcase & Deployment Guide

Three ways to put SwingLens in front of judges, from fastest to most public.
Everything here uses free tiers only. The app is a **single service**: the
backend serves both the API and the built frontend on one port.

> LLM note: cloud hosts can't run Ollama. Either (a) leave the AI chat in its
> honest offline state — **the analyst engine, scanner, indicators, Explore,
> Pulse news, and setup cards all work with zero LLM** (they're math + real
> data), or (b) plug in a free cloud model: get a free API key from Groq
> (console.groq.com), then set `LLM_PROVIDER=cloud` and
> `CLOUD_LLM_API_KEY=...`. Costs ₹0 on their free tier.

---

## Option 1 — Any laptop, one command (Docker)

On a machine with Docker installed:

```
docker compose up --build
```

Open http://localhost:8000 — demo mode is on, so the login page shows
**✨ Try the demo account** (demo@swinglens.app / swingdemo123). Data
persists in a named volume. To share on the venue WiFi, give people
`http://<your-ip>:8000`.

No Docker on the hackathon machine? The manual path in README.md
(Python + Node) works exactly as before.

---

## Option 2 — Public URL on Render (free)

1. Push the project to a GitHub repo.
2. On render.com → New → **Web Service** → connect the repo.
3. Environment: **Docker** (it auto-detects the Dockerfile). Instance type: **Free**.
4. Add environment variables:
   - `DEMO_MODE=1`
   - `SECRET_KEY=<any long random string>`
   - optional: `LLM_PROVIDER=cloud`, `CLOUD_LLM_API_KEY=<free Groq key>`
5. Deploy → you get `https://your-app.onrender.com` that opens on anyone's
   laptop, exactly like a Vercel link.

Honest limits of the free tier: the service **sleeps after ~15 min idle and
cold-starts in ~1 minute** — open it once before your demo slot. Free
instances also have modest CPU; the first market scan takes a bit longer.

## Option 2b — Hugging Face Spaces (free, no sleep)

Create a **Docker** Space, push this repo into it, and in the Space's
`README.md` front-matter set `app_port: 8000` (or set a `PORT` env var —
the container respects it). Add the same environment variables under
Settings → Variables. Free CPU Spaces don't sleep the way Render does.

> Why not Vercel? Vercel is built for frontends/serverless — it can't run
> this persistent FastAPI+SQLite service. Render/HF Spaces give you the same
> "open my URL" experience for full-stack apps, free.

---

## Environment variables (all optional except SECRET_KEY in public deploys)

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | 0 | `1` seeds demo account + login button |
| `DEMO_PASSWORD` | swingdemo123 | demo account password |
| `SECRET_KEY` | dev value | JWT signing — set a real one publicly |
| `DATABASE_URL` | sqlite file | Postgres URL works unchanged (SaaS phase) |
| `LLM_PROVIDER` | ollama | `cloud` for OpenAI-compatible APIs |
| `CLOUD_LLM_BASE_URL` | Groq endpoint | any /chat/completions provider |
| `CLOUD_LLM_API_KEY` | (empty) | free at console.groq.com |
| `CLOUD_LLM_MODEL` | llama-3.1-8b-instant | provider model name |

---

## The 3-minute judge demo script

1. **Login page** → tap *Try the demo account* (nobody registers at a demo).
2. **Pulse** loads: real drifting headlines, each labeled CONFIRMED ×N
   sources or UNVERIFIED — say the line: *"nothing on this screen was
   written by an AI; every card links to the original article."*
3. **Explore** → Indian Stocks → Mid Cap → click a top gainer.
4. Chart opens → press **Analyze** → zones, trendlines, ENTRY/STOP/T1/T2
   draw themselves; scroll to the setup card → point at the **confidence
   factor breakdown** and the *"✓ Verified against data"* badge.
5. In the chat: type **"scan the market for bullish setups"** → the engine
   ranks the whole universe live, with the *Techniques applied* checklist
   open — say: *"the AI never picks stocks; the math does, and the AI only
   explains it."*
6. Close with the Sources footer on any panel: provider, link, timestamp.

That narrative — **transparency as the product** — is your differentiator.
