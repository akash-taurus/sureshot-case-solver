# Sureshot — the case-solving algorithm, as a tool

An AI-powered Streamlit app that runs **THE SURESHOT CASE-SOLVING ALGORITHM** (see `flow.md`) on any case-competition prompt or consulting case. Paste the prompt, run the five phases with an LLM, steer the output, and export a full case package.

## The workflow

| Step | What the tool produces |
|------|------------------------|
| **1. Deconstruct** | Colour-coded breakdown of the prompt (objective / constraints / data / deliverables), slide-limit detection, core-issue classification, decision log |
| **2. Strategic setup** | Initial hypothesis + confirm/falsify tests, standard or customised framework, MECE issue tree (mermaid diagram + outline) |
| **3. Research & ideation** | 5-layer research plan (company → industry → customer → competitors → misc), findings synthesis from your own notes, brainstorm + F.I.A. filter, pre-mortem |
| **4. The build** | SCQA executive summary, action titles, slide-by-slide outline honouring the slide limit, financial story, implementation roadmap, appendix plan |
| **5. Delivery & defense** | Speaker hand-offs with exact lines, 10 likely judge questions with answers, rules of engagement, post-event checklist |
| **6. Export** | One Markdown package (case package) with every phase + the Sureshot quality checklist, ready to download and share |

Extra touches: a time-budget clock with per-phase targets (10% / 30% / 60% / 80% / 100% of your budget), per-phase steering feedback for regeneration, and editable results.

## Setup

1. **Get a free API key** (either or both — switch with one click in the sidebar):
   - **Groq (recommended)** — [console.groq.com/keys](https://console.groq.com/keys). In head-to-head testing, Groq was ~4-6x faster than NIM and produced sharper analysis. Default model: `openai/gpt-oss-120b`.
   - **NVIDIA NIM** — [build.nvidia.com](https://build.nvidia.com) → *API Keys* → *Create*.

2. **Install dependencies** (Python 3.11+):

   ```bash
   pip install -r requirements.txt
   ```

3. **Provide the key(s)** — either:
   - paste it into the sidebar at runtime, or
   - copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set `groq_api_key` / `nvidia_api_key`.

4. **Run the app**:

   ```bash
   streamlit run streamlit_app.py
   ```

## Deploy on Streamlit Community Cloud (free)

The repo is deploy-ready — [share.streamlit.io](https://share.streamlit.io) → **Create app** → *Deploy a public app from GitHub*:

1. **Repository:** `akash-taurus/sureshot-case-solver`, branch `main`, main file path `streamlit_app.py`.
2. **Advanced settings** → pick **Python 3.12** (or newer) and paste the **Secrets** (same TOML shape as `.streamlit/secrets.toml`):

   ```toml
   groq_api_key = "gsk_…"
   nvidia_api_key = "nvapi-…"
   ```

3. **Deploy.** First build takes a few minutes.

Two things to know:

- **The key in Secrets is shared by everyone who opens the app** (the app pre-fills it). On a public URL that means your free-tier quota is public too. Either leave `groq_api_key` out and let visitors paste their own key in the sidebar, or keep the URL to yourself.
- Free apps sleep after prolonged inactivity; the first visit afterwards wakes them in ~30-60s.

## Using it

1. In the sidebar: confirm key + model (the model list is fetched live from the endpoint; any model id can be typed), set your time budget, team size, and slide limit (0 = auto-detect in Phase 1).
2. Hit **Start timer**, then run each phase in order. Click *Load sample case* to try a practice case immediately.
3. Not happy with a phase? Type **steering feedback** and hit *Regenerate*. You can also switch the result onto **Edit** and fix the Markdown by hand.
4. When done, open **6. Export** and download the `.md` package.

## Notes

- **Provider presets** — the sidebar's *Provider preset* switch flips between Groq and NVIDIA NIM (base URL, key from secrets, and default model all swap together). Any OpenAI-compatible endpoint works too: edit *Base URL* and paste a key manually (OpenAI, OpenRouter, …).
- Free tiers have rate limits and occasional temporary key restrictions; each phase is one request, so normal use is fine.
- Keep results sharp by regenerating with steering feedback instead of hammering the API (free-tier rate limits).
- The model is instructed never to invent precise statistics — unverified claims come out tagged `[verify]` or `[estimate]`, per the algorithm's triangulation rule.
- `flow.md` is the source of truth for the phase content; `sureshot/phases.py` and `sureshot/prompts.py` encode it.

## Troubleshooting

| Symptom | What it means | Fix |
|---|---|---|
| `410 Gone` — "model has reached its end of life" | NVIDIA retires models regularly (e.g. `meta/llama-3.3-70b-instruct` died 2026-08) | Pick a current model from the live list in the sidebar |
| `403 Forbidden` — "Authorization failed" on chat, while the model list still loads | Free-tier rate limit / temporary key restriction (a known trial-key behaviour) | Wait a few minutes and retry; if it persists for hours, create a fresh key at build.nvidia.com |
| `429 Too Many Requests` | Rate limit reached | Wait ~15s and retry; avoid rapid-fire regenerations |
| `413` — "Request too large … on tokens per minute (TPM)" | By late phases the context (case + all prior phases) exceeds the free tier's per-minute token cap (Groq gpt-oss-120b: 8,000 TPM, counting input + reserved output). The app already trims context automatically | Lower *Max output tokens* in the sidebar (Groq preset uses 3072), shorten notes, or switch model/provider |
| First token takes 30–60s | Cold start of the model on the free tier | Wait — streaming will start; the app shows a "thinking" indicator meanwhile |
| Model missing from the sidebar list | It isn't enabled for your key | Type a different model id, or check the provider console for what your account can access |

## Project layout

```
streamlit_app.py          # wizard UI: sidebar setup, phase stepper, export page
sureshot/
  phases.py               # phase metadata (goals, steps, time shares) from flow.md
  prompts.py              # per-phase system prompts + user-message assembly
  llm.py                  # OpenAI-compatible client, streaming, model listing
  export.py               # case-package Markdown builder
.streamlit/
  config.toml             # theme
  secrets.toml.example    # key template (copy to secrets.toml — git-ignored)
flow.md                   # the algorithm itself
```
