## VoxAssist — Real-Time Voice IT Helpdesk Agent

Product Requirements Document · StarForge 2026 Hackathon · Track: VoxForge — Real-Time Voice Agents

|   | Track VoxForge — Real-Time Voice Agents Event StarForge 2026 (E-Cell JSS Noida) Doc Status Draft v1.0 Date August 2026 |   |
| --- | --- | --- |
|   | Core Partners Rime (Voice), Qdrant (Retrieval) Submission Round 1 — PPT + Video + GitHub Data Layer Qdrant + MongoDB + Redis |   |

## 1. Problem Statement

Employees routinely lose 15–45 minutes waiting in IT support ticket queues for issues that have already been solved dozens of times before — VPN drops, Wi-Fi disconnects, password resets, MFA lockouts, printer failures. Existing self-serve options (FAQ portals, chatbots) are slow to use, require precise typing of technical symptoms, and don't feel conversational enough for a quick "walk me through it" interaction while a user is mid-task, often away from a keyboard.

VoxAssist is a real-time, interruptible voice agent that lets an employee simply talk through their IT issue out loud, get walked through a fix conversationally, correct the agent mid-sentence if it misunderstands, and get escalated to a human technician automatically when the issue can't be resolved — all with natural, low-latency, spoken interaction.

## 2. Goals & Non-Goals

| Goals | Non-Goals |
| --- | --- |
| Resolve common IT issues via natural spoken conversation | Replacing the full IT ticketing system |
| Support real interruptions / barge-in mid-response | Handling every possible IT issue (KB scoped to demo set) |
| Ground every answer in a real, retrievable knowledge base | Enterprise-grade authentication / SSO integration |
| Escalate to a human ticket when unresolved | Multi-language support (English-first for MVP) |
| Feel low-latency and "alive," not like a scripted IVR | Production-hardened security / compliance certification |

## 3. Target User & Use Case

| Persona | Context | Need |
| --- | --- | --- |
| Office employee | Working, often hands-busy or away from a support portal | Fast, spoken troubleshooting without typing a ticket |
| Remote / field worker | Connectivity issues are the actual problem being reported | A voice-first channel that doesn't assume a stable text UI |
| IT support team | Overloaded with repetitive, low-complexity tickets | Deflect resolvable issues; only see escalated, real problems |

## 4. Core User Flow

- 1. User opens the app and taps to start talking — no typing required.

- 2. User describes the issue in natural speech (e.g. "My VPN keeps disconnecting").

- 3. Agent begins a spoken response while simultaneously retrieving relevant troubleshooting content from the knowledge base.

- 4. User interrupts mid-response to correct or redirect ("Wait, actually it's my Wi-Fi, not VPN") — agent stops immediately, acknowledges, and adapts.

- 5. Agent walks through fix steps conversationally, one step at a time, confirming before moving on.

- 6. If resolved: agent confirms and ends the session.

If unresolved after N attempts: agent creates an escalation ticket via a tool call and informs the user a technician will follow up.

Demo signal to judges: the interruption moment (step 4) is the single most important beat to nail — it is the clearest, most visible proof of "real-time" behavior in a 2-minute video.

## 5. Functional Requirements

| ID | Requirement | Description | Priority |
| --- | --- | --- | --- |
| FR-1 | Streaming speech input | Continuously transcribe user audio with partial/interim results | Must-have |
| FR-2 | Turn / silence detection | Detect when the user has finished a turn vs. is pausing to think | Must-have |


| FR-3 | Barge-in / interruption | Detect speech while agent is talking; cancel active generation and TTS instantly | Must-have |
| --- | --- | --- | --- |
| FR-4 | Retrieval-grounded responses | Every troubleshooting answer is grounded in a KB doc fetched from Qdrant, not | Must-have |
|   |   | hallucinated |   |
| FR-5 | Streaming voice output | Rime TTS begins speaking before the full response text is generated | Must-have |
| FR-6 | Session memory | Agent remembers earlier turns in the same session (device, issue, steps already tried) | Should-have |
|   |   | — held in Redis for fast access |   |
| FR-7 | Escalation tool call | Agent can invoke a "create_ticket" tool when it cannot resolve the issue; ticket is | Must-have |
|   |   | persisted in MongoDB |   |
| FR-8 | Reconnect handling | Session state persists in Redis through a dropped connection; user can resume without | Should-have |
|   |   | losing context |   |
| FR-9 | Visual state feedback | Robot-face UI reflects agent state (listening / thinking / speaking / interrupted) via eyes | Must-have |
|   |   | and mouth motion — no transcript shown |   |
| FR-10 | Similar-ticket lookup | Qdrant retrieves prior resolved tickets similar to the current issue for faster resolution | Nice-to-have |

## 6. Non-Functional Requirements

| Category | Target |
| --- | --- |
| Perceived latency | < 1.2s from end of user speech to start of agent's spoken reply |
| Interruption response | < 300ms from detected barge-in to agent audio stopping |
| Reliability | Graceful fallback / apology on STT, LLM, or TTS failure — never a silent hang |
| Data handling | No real employee credentials or PII; synthetic/de-identified data only |
| Security | No API keys or secrets committed to the repo; environment variables only |

## 7. System Architecture

```
Mic Input (Web Audio API / WebRTC)
|
v
Streaming STT ---------------------------+
(Whisper API / Deepgram) |
| |
v |
VAD / Turn Detector (Silero VAD) | continuous listening
| | even while agent speaks
v |
Interrupt Controller <--------------------+
- cancels active LLM stream (pub/sub signal via Redis)
- cancels active Rime TTS stream
- flips UI state to "Interrupted"
|
v
Redis <--- live session state (state, last turns, device context)
| read/write on every turn, powers reconnect (FR-8)
v
LLM Orchestrator (OpenAI, streaming + tool calling)
|
+--> Qdrant ---search---> MongoDB
| (finds relevant (returns full doc content:
| doc/ticket IDs KB article text, past
| via vector search) ticket details, etc.)
|
+--> Tool: create_ticket()
| writes full ticket record --> MongoDB
| (+ embeds summary --> Qdrant, for future similarity search)
|
v
Rime Streaming TTS ---> Audio Output
|
v
Robot-Face UI (state-driven eyes/mouth animation)
On session end: Redis session state archived --> MongoDB (conversation log)
```

## 8. Technology Stack

## 8.1 Required Partner Technologies


| Component | Technology | Role |
| --- | --- | --- |
| Voice generation | Rime | Core TTS engine — generates all spoken agent output via streaming endpoint so speech starts |
|   |   | before full text generation completes. Must remain the sole audio source (no other TTS engine |
|   |   | used). |
| Retrieval / memory | Qdrant | Vector search over the IT knowledge base and similar-ticket lookup. Returns document IDs by |
|   |   | semantic similarity; functionally required for grounding answers and enabling escalation context. |

## 8.1.1 Supporting Data Stores

Qdrant handles semantic search only. Two additional stores round out the data layer — each solving a distinct problem rather than duplicating Qdrant's role:

| Component | Technology | Role |
| --- | --- | --- |
| Structured storage | MongoDB | Source-of-truth for KB articles, escalation tickets, and archived conversation logs. Qdrant stores |
|   |   | only embeddings + a pointer (document ID); MongoDB stores and returns the actual content |
|   |   | once Qdrant identifies what's relevant. |
| Live session state | Redis | Millisecond-latency read/write for the active session: current agent state |
|   |   | (listening/thinking/speaking/interrupted), short-term conversation memory, and device context. |
|   |   | Powers reconnect handling (FR-8) and barge-in signaling via pub/sub. |

## 8.2 Supporting Stack

| Layer | Technology Choice | Notes |
| --- | --- | --- |
| LLM / reasoning | OpenAI (GPT-4o or similar, streaming) | Response generation + tool calling for escalation |
| Speech-to-text | Whisper API (fallback: Deepgram / | Needs low-latency streaming; benchmark before locking in |
|   | AssemblyAI) |   |
| Turn / voice-activity detection | Silero VAD (or WebRTC VAD) | Drives turn-end and barge-in detection |
| Transport | WebSockets | Full-duplex audio streaming between client and backend |
| Backend | Python (FastAPI) or Node.js | Hosts STT/LLM/TTS orchestration pipeline |
| Frontend | HTML / CSS / JS (Web Audio API) | Robot-face UI with animated eyes/mouth, no transcript panel |
| Embeddings | OpenAI embeddings API | Used to embed IT KB documents and tickets into Qdrant |
| Structured storage | MongoDB | KB articles, escalation tickets, archived conversation logs |
| Session cache | Redis | Live session state, short-term memory, reconnect support, interrupt |
|   |   | signaling |
| Hosting | Any (local demo acceptable for hackathon) | Must be runnable via README instructions |

## 8.3 Data Store Schemas (indicative)

```
MongoDB — kb_articles
{
_id: ObjectId,
title: "VPN keeps disconnecting",
category: "network",
steps: [ "Check adapter settings...", "Restart VPN client..." ],
updated_at: ISODate
}
MongoDB — tickets
{
_id: ObjectId,
session_id: "abc123",
issue_summary: "Wi-Fi drops every few minutes",
steps_tried: [...],
status: "escalated",
transcript_summary: "...",
created_at: ISODate
}
Redis — session:{session_id}
{
state: "speaking", # idle|listening|thinking|speaking|interrupted
last_turns: [ {role, text}, ... ],
device_context: "Windows 11, VPN client v4.2",
ticket_draft: {...}
}
TTL: session lifetime; archived to MongoDB on session end
Qdrant — kb_vectors / ticket_vectors
{
id: ,
vector: [ ...embedding... ],
```


## 9. Robot-Face UI Specification

Replaces a text transcript with a single animated robot face as the entire visual surface. State is communicated purely through eye and mouth motion plus a subtle color/glow shift.

| State | Eyes | Mouth | Trigger |
| --- | --- | --- | --- |
| Idle | Neutral, slow blink | Closed, still | No active session |
| Listening | Widen slightly, track subtly | Closed | User is speaking (mic active) |
| Thinking | Narrow / soft pulse | Closed, slight tilt | Waiting on LLM / Qdrant |
|   |   |   | retrieval |
| Speaking | Relaxed | Animates in sync with TTS audio amplitude | Rime audio is playing |
| Interrupted | Snap wide, quick blink | Stops mid-motion abruptly | Barge-in detected while |
|   |   |   | speaking |
| Escalating | Soft amber glow | Closed | create_ticket tool call fired |

## 10. Knowledge Base Scope (Demo Set)

Seed content for Qdrant retrieval, sized for a convincing hackathon demo (10–20 documents):

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

## 12. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Interruption handling proves too complex under | Build and validate this first, before KB integration or UI polish; treat it as the critical path |
| time pressure |   |
| Whisper API latency too high for real-time feel | Benchmark early; fall back to Deepgram/AssemblyAI streaming STT if needed |
| Qdrant role feels bolted-on rather than functional Visibly surface retrieved KB doc in agent's reasoning / escalation ticket content so its role is demonstrable |   |
| Rime diluted by other audio sources | Enforce Rime as the only TTS engine in the pipeline; no fallback TTS |
| Demo video fails to show interruption clearly | Script and rehearse the exact interrupt moment; rely on robot-face state change as visual proof |
| Too many moving data stores (Qdrant + | Build Qdrant first (mandatory). Session state can start as an in-memory dict and upgrade to Redis once the |
| MongoDB + Redis) for hackathon timeline | core loop works. MongoDB can be mocked with a JSON file initially and noted as a "next step" in Limitations |
|   | if time runs out |

## 13. Submission Checklist

- Public GitHub repository with problem statement, solution explanation, architecture diagram

- Working proof: at least one live feature demo or reproducible test

- README with clear setup and run instructions

- Limitations section (what does / does not work)

- Team contributions documented


- Round 1: Official PPT template, 2-minute video, Drive link, team details

- No exposed API keys / credentials in repo

VoxAssist PRD — StarForge 2026 · VoxForge Track · Draft v1.0
