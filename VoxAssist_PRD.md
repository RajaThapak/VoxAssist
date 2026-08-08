## VoxAssist — Real-Time Voice IT Helpdesk Agent

Product Requirements Document · StarForge 2026 Hackathon · Track: VoxForge — Real-Time Voice Agents

|   | Track VoxForge — Real-Time Voice Agents Event StarForge 2026 (E-Cell JSS Noida) Doc Status Updated — reflects actual implementation Date August 2026 |   |
| --- | --- | --- |
|   | Core Partners Rime (Voice), Qdrant (Retrieval) Submission Round 1 — PPT + Video + GitHub Data Layer Qdrant + MongoDB + Redis |   |

> **Note on this revision:** This document was updated after implementation to reflect what was actually built, not just what was originally planned. Where the build diverged from the original plan — either falling short or going beyond it — that's called out explicitly rather than silently edited away, so the gap between plan and reality stays visible.

## 1. Problem Statement

Employees routinely lose 15–45 minutes waiting in IT support ticket queues for issues that have already been solved dozens of times before — VPN drops, Wi-Fi disconnects, password resets, MFA lockouts, printer failures. Existing self-serve options (FAQ portals, chatbots) are slow to use, require precise typing of technical symptoms, and don't feel conversational enough for a quick "walk me through it" interaction while a user is mid-task, often away from a keyboard.

VoxAssist is a real-time, interruptible voice agent that lets an employee simply talk through their IT issue out loud, get walked through a fix conversationally, correct the agent mid-sentence if it misunderstands, and get escalated to a human technician automatically when the issue can't be resolved — all with natural, low-latency, spoken interaction.

## 2. Goals & Non-Goals

| Goals | Non-Goals |
| --- | --- |
| Resolve common IT issues via natural spoken conversation | Replacing the full IT ticketing system |
| Support interruptions / barge-in mid-response (manual trigger, not automatic VAD — see FR-3) | Handling every possible IT issue (KB scoped to demo set) |
| Ground every answer in a real, retrievable knowledge base (real vector search — see FR-4) | Enterprise-grade authentication / SSO integration |
| Escalate to a human ticket when unresolved | Production-hardened security / compliance certification |
| Multi-language conversation — auto-detected, no manual toggle (built beyond original scope; see FR-11) | Session reconnect after a dropped connection (see FR-8) |

## 3. Target User & Use Case

| Persona | Context | Need |
| --- | --- | --- |
| Office employee | Working, often hands-busy or away from a support portal | Fast, spoken troubleshooting without typing a ticket |
| Remote / field worker | Connectivity issues are the actual problem being reported | A voice-first channel that doesn't assume a stable text UI |
| IT support team | Overloaded with repetitive, low-complexity tickets | Deflect resolvable issues; only see escalated, real problems |

## 4. Core User Flow

- 1. User taps "Start Session" — no typing required (though a text input is also available as a fallback/testing channel).

- 2. User describes the issue in natural speech (e.g. "My VPN keeps disconnecting"), transcribed via the browser's built-in speech recognition.

- 3. Agent retrieves relevant KB content via Qdrant vector search, then generates a spoken response — retrieval happens *before* generation (not simultaneously with speaking, as originally envisioned; see FR-4/FR-5 status below).

- 4. User can interrupt via the "Interrupt Agent" button — agent stops immediately, acknowledges, and adapts. (Automatic barge-in by speaking over the agent was not implemented — see FR-3.)

- 5. Agent walks through fix steps conversationally, one step at a time, confirming before moving on.

- 6. If resolved: agent asks a varied closing question ("is your work done?"), and on confirmation speaks a randomized farewell and ends the session. This two-step confirm-then-close flow is enforced deterministically in code (not left purely to the LLM's judgment) after early testing showed the model didn't reliably call its own "end session" tool on the first pass.

If unresolved after all KB steps are exhausted, or the user asks for a human: agent creates an escalation ticket via a tool call and informs the user a technician will follow up.

Demo signal to judges: the interruption moment (step 4) is still the clearest, most visible proof of "real-time" behavior — worth noting it's a button-triggered interrupt, not voice-detected, when framing the demo.

## 5. Functional Requirements

| ID | Requirement | Description | Priority | Status |
| --- | --- | --- | --- | --- |
| FR-1 | Speech input | Transcribe user audio | Must-have | **Partial** — uses the browser's built-in Web Speech API (final transcripts only, no partial/interim streaming). A Whisper API client exists in the codebase but isn't wired into the live path. |
| FR-2 | Turn / silence detection | Detect when the user has finished a turn | Must-have | **Implemented** — via the browser recognizer's own end-of-speech detection, not a custom silence/VAD model. |
| FR-3 | Barge-in / interruption | Cancel active generation and TTS on interruption | Must-have | **Partial** — interruption itself (cancelling the LLM task, stopping audio) works and is fast, but it's triggered by clicking "Interrupt Agent," not by automatically detecting the user speaking over the agent. True automatic barge-in would need continuous raw audio streaming to the backend plus a VAD model (e.g. Silero) — not built. |
| FR-4 | Retrieval-grounded responses | Every troubleshooting answer is grounded in a KB doc via real vector search | Must-have | **Implemented** — KB articles are embedded with OpenAI's `text-embedding-3-small` and queried via real Qdrant vector search (not keyword matching). Falls back to keyword/topic matching if Qdrant or the embeddings API is unavailable. |
| FR-5 | Streaming voice output | Rime TTS begins speaking before the full response text is generated | Must-have | **Not implemented as specified** — Rime now generates and plays *real* audio (a real gap from the original build — see Risks), but synthesis waits for the complete reply text rather than starting mid-generation. Per-sentence streaming synthesis was built and measured, then reverted: Rime has a large fixed per-call latency floor (~1.5–2.2s, almost independent of text length), so splitting one reply into multiple Rime calls made total latency *worse*, not better. |
| FR-6 | Session memory | Agent remembers earlier turns in the same session | Should-have | **Implemented** — held in Redis (falls back to an in-memory dict if Redis is unavailable). |
| FR-7 | Escalation tool call | Agent can invoke a `create_ticket` tool when it cannot resolve the issue | Must-have | **Implemented** — persisted in MongoDB (in-memory fallback if unavailable). |
| FR-8 | Reconnect handling | Session state persists through a dropped connection; user can resume | Should-have | **Not implemented** — a new random session ID is generated on every WebSocket connection, so a dropped connection cannot resume prior context even though the underlying Redis session state exists. |
| FR-9 | Visual state feedback | Robot UI reflects agent state via animation, no transcript shown | Must-have | **Implemented, redesigned** — see Section 9. The visual language (minimal LED-face robot) differs substantially from the original "expressive eyes/mouth" concept but serves the same purpose. |
| FR-10 | Similar-ticket lookup | Qdrant retrieves prior resolved tickets similar to the current issue | Nice-to-have | **Not implemented** — Qdrant only indexes the KB articles; past tickets aren't embedded or searched. |
| FR-11 | Multi-language conversation | Understand and respond in the user's language, auto-detected | *(added — not in original scope)* | **Implemented** — the LLM mirrors whichever language the user writes/speaks in (any language, not a fixed list). Speech recognition and the spoken-voice selection auto-adapt to the detected language of the conversation, with no manual toggle. First-utterance recognition accuracy for a language the session hasn't seen yet is the known limitation (see Risks). |
| FR-12 | Real-time lip sync | Mouth animation matches actual spoken audio | *(added — not in original scope)* | **Implemented** — driven by live RMS amplitude analysis of the real Rime audio waveform via the Web Audio API, not simulated/random amplitude. |

## 6. Non-Functional Requirements

| Category | Target | Actual |
| --- | --- | --- |
| Perceived latency | < 1.2s from end of user speech to start of agent's spoken reply | **~5–8s measured**, dominated by GPT-4o's non-streaming-to-audio completion (~2–4.6s) and Rime's fixed per-call synthesis overhead (~1.5–2.2s). See Risks for why the streaming fix was reverted rather than kept. |
| Interruption response | < 300ms from detected barge-in to agent audio stopping | Stopping itself is near-instant on click; there's no "detection" latency to measure since barge-in isn't voice-triggered (see FR-3). |
| Reliability | Graceful fallback on STT, LLM, or TTS failure — never a silent hang | **Met, and extended** — every external dependency (Redis, MongoDB, Qdrant, OpenAI, Rime) degrades gracefully to a local/offline fallback rather than failing the session. |
| Data handling | No real employee credentials or PII; synthetic/de-identified data only | Met — demo persona ("Alex Johnson") only. |
| Security | No API keys or secrets committed to the repo; environment variables only | Met — `.env` is gitignored and confirmed excluded before the repo was made public on GitHub. |

## 7. System Architecture (as built)

```
Browser Mic Input
|
v
Web Speech API (browser-native STT)
- final transcripts only, no partial streaming
- language auto-set from detected conversation language
|
v
WebSocket (FastAPI backend)
|
v
Redis <--- session state (state, last turns, current KB step,
|            awaiting_close_confirmation flag)
v
Qdrant KB Search
- query embedded via OpenAI text-embedding-3-small
- real vector search against embedded KB articles
- falls back to keyword/topic matching if unavailable
|
v
LLM Orchestrator (OpenAI GPT-4o, streamed text accumulation)
- tools: create_ticket, end_session
- deterministic backstop: if the agent's last message looked like a
  closing question and the user now confirms, the session closes in
  code without relying on the LLM to call end_session reliably
|
+--> Tool: create_ticket() --> MongoDB (ticket record)
|
v
Rime TTS (single call per full reply)
- primary voice engine; real audio played via Web Audio API
- real-time RMS waveform analysis drives lip-sync animation
- on failure/unsupported language: falls back to the browser's
  own speech synthesis voice, matched to the detected language
|
v
Robot-Avatar UI (state-driven CSS/SVG animation, no transcript panel)

Manual interrupt (button click):
- cancels the active asyncio task running the turn
- stops audio playback (Rime <audio> element or browser TTS)
- flips UI state to "Interrupted"

Not built: continuous audio streaming to the backend, VAD-based
automatic barge-in, session reconnect/resume, similar-ticket search.
```

## 8. Technology Stack (as built)

### 8.1 Required Partner Technologies

| Component | Technology | Role — as built |
| --- | --- | --- |
| Voice generation | Rime | Primary TTS engine — synthesizes one complete audio clip per reply (not streamed mid-generation) and is played directly in the browser via the Web Audio API. Falls back to the browser's own speech synthesis only when Rime is unavailable or doesn't support the detected language. |
| Retrieval / memory | Qdrant | Real vector search over the IT knowledge base using OpenAI embeddings — genuinely functional (not keyword-matching dressed up as semantic search). Similar-ticket lookup (FR-10) was not built. |

### 8.1.1 Supporting Data Stores

| Component | Technology | Role |
| --- | --- | --- |
| Structured storage | MongoDB | Source-of-truth for KB articles and escalation tickets. In-memory fallback if unavailable. |
| Live session state | Redis | Active session state, conversation history, closing-confirmation flag. In-memory fallback if unavailable. Reconnect handling (FR-8) was not built on top of this. |

### 8.2 Supporting Stack

| Layer | As built | Notes vs. original plan |
| --- | --- | --- |
| LLM / reasoning | OpenAI GPT-4o, `stream=True` | Text streams in from the API, but audio synthesis still waits for the full accumulated reply (see FR-5). |
| Speech-to-text | Browser Web Speech API | Whisper API client exists in the codebase but is unused; original plan was Whisper/Deepgram streaming STT. |
| Turn / voice-activity detection | Browser recognizer's built-in endpointing | Silero/WebRTC VAD was not built. |
| Transport | WebSockets | As planned. |
| Backend | Python (FastAPI) | As planned. |
| Frontend | HTML / CSS / JS (Web Audio API, Canvas) | Robot-avatar UI redesigned from the original spec (see Section 9); added an animated canvas network background. |
| Embeddings | OpenAI `text-embedding-3-small` | As planned, and actually wired up (see FR-4). |
| Structured storage | MongoDB | As planned. |
| Session cache | Redis | As planned, minus reconnect handling. |
| Hosting | Local | Runnable via `python -m backend.main`; not deployed. |

## 9. Robot-Avatar UI Specification (as built)

The original "expressive eyes/mouth on an abstract face" concept was redesigned into a minimal LED-style robot avatar: a rounded-square off-white head with a small antenna, two side ear modules, and a dark charcoal face panel holding two vertical cyan LED "pill" eyes and one horizontal cyan LED "pill" mouth. No eyebrows, no realistic facial features — deliberately minimal and iconic. State is communicated through eye/mouth pill sizing, ear-pulse animation, and an outer glow ring color, all still with no transcript shown.

| State | Eyes | Mouth | Ears | Trigger |
| --- | --- | --- | --- | --- |
| Idle | Neutral size, slow blink | Small closed pill | Static | No active session |
| Listening | Slightly taller pill, gentle breathing opacity pulse | Small closed pill | Pulse taller/shorter on a loop, as if perking up | Mic is active |
| Thinking | Shorter pill, gentle scale/opacity pulse | Small closed pill | Static | Waiting on LLM / Qdrant retrieval; whole head subtly tilts side to side |
| Speaking | Neutral size | Morphs width/height in real time from actual Rime audio amplitude (RMS analysis via Web Audio API) | Static | Audio is playing |
| Interrupted | Snaps taller briefly, then settles | Snaps to closed pill immediately | Static | Barge-in button clicked while speaking |
| Escalating | Neutral size | Small closed pill | Static | Amber glow on the outer ring; `create_ticket` tool call fired |

## 10. Knowledge Base Scope (Demo Set)

Unchanged from the original plan — 10 seed articles indexed for Qdrant retrieval:

- VPN disconnects / authentication failures
- Wi-Fi drops / weak signal troubleshooting
- Password reset flow
- MFA lockout recovery
- Printer not found / offline
- Slow laptop performance
- Software install requests
- Email sync issues
- VDI / remote desktop login failures
- Low disk space warnings

## 11. Success Metrics (for demo & scoring alignment)

| 30% | 25% | 20% | 15% |
| --- | --- | --- | --- |
| Problem & usefulness | Voice experience | Use of Rime | Technical execution |

Additional 10% — Demo clarity. Weightings per official StarForge 2026 VoxForge rubric.

## 12. Risks & Mitigations (updated)

| Risk | Status / Mitigation |
| --- | --- |
| Qdrant role feels bolted-on rather than functional | **Resolved.** Real OpenAI embeddings + real Qdrant vector search, verified with paraphrased test queries that share no literal keywords with the KB and still retrieve the correct article. |
| Rime diluted by other audio sources | **Deliberate, documented trade-off, not a violation.** Rime is the primary and default voice for every reply; the browser's own speech synthesis is used only as an explicit fallback when Rime fails or doesn't support the detected language (Rime is English-focused). |
| Perceived latency exceeds target (< 1.2s) | **Open, understood, not fully solved.** Measured ~5–8s per turn. Root cause: GPT-4o's completion (non-streamed to audio) and Rime's fixed per-call latency floor are both multi-second and currently run strictly sequentially. A per-sentence streaming pipeline was built and measured, then reverted after it made total latency *worse* — Rime's per-call overhead (~1.5–2.2s, almost flat regardless of text length) meant splitting a reply into more Rime calls multiplied that overhead rather than hiding it. A real fix would need either a genuinely low-latency Rime streaming endpoint or a different TTS provider. |
| Barge-in requires a manual click, not automatic voice detection | **Open, understood, not solved.** True automatic barge-in needs continuous raw audio streaming from the browser to the backend plus a VAD model running on it — a bigger architecture addition than fit in scope. Current interruption is instant once triggered, just not self-triggered by the user talking over the agent. |
| Demo video fails to show interruption clearly | Unchanged — script and rehearse the interrupt moment; note in the script that it's a button-triggered demo of the interrupt *mechanism*, not of automatic detection. |
| No session reconnect (FR-8) | **Open, not solved.** Redis session state exists and could support this, but a dropped WebSocket connection currently starts a fresh session ID with no resume path. |
| Whisper API latency too high for real-time feel | **Moot** — Whisper was never wired into the live path; STT runs entirely in the browser instead. |

## 13. Submission Checklist

- [x] Public GitHub repository — https://github.com/RajaThapak/VoxAssist
- [ ] Problem statement, solution explanation, architecture diagram in repo/PPT
- [x] Working proof: reproducible locally via `python -m backend.main`
- [ ] README with clear setup and run instructions
- [x] Limitations section (this document, Section 12)
- [ ] Team contributions documented
- [ ] Round 1: Official PPT template, 2-minute video, Drive link, team details
- [x] No exposed API keys / credentials in repo — `.gitignore` excludes `.env`, verified before the initial push

VoxAssist PRD — StarForge 2026 · VoxForge Track · Updated post-implementation
