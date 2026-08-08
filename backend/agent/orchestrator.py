import json
import random
import base64
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple
from openai import AsyncOpenAI

from backend.config import settings
from backend.storage.redis_session import session_store
from backend.storage.mongo_db import mongo_store
from backend.rag.qdrant_kb import qdrant_manager
from backend.tts.rime_tts import rime_tts
from backend.vad.interrupt import InterruptController
from backend.agent.tools import CREATE_TICKET_TOOL_SPEC, END_SESSION_TOOL_SPEC, execute_create_ticket

logger = logging.getLogger("voxassist.orchestrator")

SYSTEM_PROMPT = """You are VoxAssist, a real-time voice IT Helpdesk Agent for enterprise employees.

CORE CONVERSATIONAL GUIDELINES:
1. Detect whichever language the user is writing or speaking in — English, Hindi, Spanish, French, or any other language/script — and reply fluently and naturally in that exact same language. Never mix languages within a single reply, and only switch language if the user switches first.
2. Speak naturally, concisely, and conversationally (max 25-30 words per turn).
3. Never output markdown formatting, bullet points, numbered lists, or bold text because your output is converted directly into spoken audio via TTS.
4. Guide the user step-by-step through a fix, giving ONE clear instruction at a time and ending with a short confirming question.
5. Ground your troubleshooting advice strictly in the provided Knowledge Base articles below (they are written in English — translate/paraphrase them naturally into whatever language the conversation is in). Do not invent technical steps.
6. If the user indicates a step didn't work, proceed to the NEXT step in the KB article.
7. If all steps fail or if the user requests human support, call the 'create_ticket' tool immediately to open an escalation ticket.
8. Once the user confirms their issue is resolved, ask a short natural closing question, in the same language as the conversation, to check if they're fully done (e.g. "Is your work done for now?") — vary the phrasing every time, never repeat the same sentence. If they confirm they're done, call the 'end_session' tool with a short, warm, varied farewell message in that same language instead of continuing to troubleshoot.

GROUNDED KNOWLEDGE BASE ARTICLES:
{kb_context}
"""

CLOSING_QUESTIONS_EN = [
    "Glad that worked! Is your work done for now?",
    "Awesome, that fixed it. Would you say your work is done here?",
    "Great, that's resolved. Is everything done on your end now?",
    "Nice, glad we sorted that out. Are you all done for today?",
    "Perfect. Is that everything, and are we good to close this out?"
]

FAREWELL_MESSAGES_EN = [
    "Wonderful, glad I could help. Ending this session now — have a great day!",
    "Perfect, all set then. Closing out this session — take care!",
    "Great, thanks for chatting with me. Wrapping up the session now — goodbye!",
    "Awesome, glad we got that sorted. I'm ending the session now — see you next time!",
    "You're all set. Closing this session now — have a wonderful rest of your day!"
]

CLOSING_QUESTIONS_HI = [
    "बढ़िया, ये तो ठीक हो गया! क्या अभी आपका काम पूरा हो गया?",
    "वाह, समस्या हल हो गई। क्या आपको कुछ और चाहिए, या हम इसे बंद कर सकते हैं?",
    "बहुत बढ़िया! क्या अभी सब कुछ ठीक है आपकी तरफ से?",
    "अच्छा हुआ ये सुलझ गया। क्या आज के लिए बस इतना ही था?",
    "परफेक्ट। क्या ये सब कुछ था, और क्या हम सेशन बंद कर सकते हैं?"
]

FAREWELL_MESSAGES_HI = [
    "बहुत खूब, मदद करके अच्छा लगा। अभी सेशन बंद कर रहे हैं — आपका दिन शुभ हो!",
    "ठीक है, सब कुछ हो गया। सेशन बंद कर रहे हैं — ध्यान रखिएगा!",
    "बढ़िया, बात करने के लिए धन्यवाद। सेशन खत्म कर रहे हैं — अलविदा!",
    "शानदार, समस्या सुलझ गई। अभी सेशन बंद कर रहे हैं — फिर मिलेंगे!",
    "आपका काम हो गया। सेशन बंद कर रहे हैं — आपका दिन अच्छा रहे!"
]

# Backward-compatible default (used as the LLM path's fallback when it omits a farewell message)
FAREWELL_MESSAGES = FAREWELL_MESSAGES_EN


def _is_hindi(text: str) -> bool:
    """True if text contains Devanagari script characters."""
    return any('ऀ' <= ch <= 'ॿ' for ch in text)


AFFIRMATIVE_KEYWORDS = [
    "yes", "yeah", "yep", "fixed", "resolved", "working", "thank", "thanks", "okay", "ok",
    "all set", "that's all", "thats all", "nothing else", "all done", "i'm done", "im done",
    "haan", "han", "theek", "thik", "sahi", "ho gaya", "हाँ", "हां", "ठीक", "धन्यवाद", "शुक्रिया", "हो गया"
]

NEGATIVE_KEYWORDS = [
    "no", "nope", "not working", "didn't work", "didnt work", "failed", "next",
    "nahi", "nahin", "kaam nahi", "नहीं", "नही"
]

# Heuristic signal that the assistant's last message was a "are you fully done?"
# closing question rather than a normal troubleshooting-step confirmation (e.g.
# "does that fix it?") — deliberately distinct wording so the two aren't confused.
CLOSING_QUESTION_SIGNALS = [
    "done for", "all done", "all set", "anything else", "is that everything", "is that all",
    "close this out", "close the session", "wrap up", "finished for", "good to go", "sorted for now",
    "काम पूरा", "आज के लिए", "कुछ और", "बंद कर", "सब कुछ"
]


def _is_affirmative_text(text: str) -> bool:
    lower = text.strip().lower()
    return any(kw in lower for kw in AFFIRMATIVE_KEYWORDS)


def _is_negative_text(text: str) -> bool:
    lower = text.strip().lower()
    return any(kw in lower for kw in NEGATIVE_KEYWORDS)


def _looks_like_closing_question(text: str) -> bool:
    lower = text.lower()
    return "?" in text and any(sig in lower for sig in CLOSING_QUESTION_SIGNALS)


class AgentOrchestrator:
    def __init__(self, session_id: str, send_ws_event: Callable[[Dict[str, Any]], Any]):
        self.session_id = session_id
        self.send_ws_event = send_ws_event
        self.interrupt_controller = InterruptController(session_id)
        self.openai_client: Optional[AsyncOpenAI] = None
        
        if settings.is_openai_live:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def process_user_turn(self, user_text: str):
        """
        Executes complete turn loop:
        1. Set state to 'thinking'
        2. Qdrant KB retrieval & session step tracking
        3. LLM streaming generation + tool call check
        4. Rime TTS speech streaming to client
        """
        try:
            # Save user turn to Redis memory
            await session_store.add_turn(self.session_id, "user", user_text)
            await session_store.set_state(self.session_id, "thinking")
            await self.send_ws_event({"type": "state_change", "state": "thinking", "user_text": user_text})

            session = await session_store.get_session(self.session_id)

            # Deterministic backstop: if we asked "are you fully done?" last turn, don't
            # rely on the LLM to reliably call the end_session tool on this turn — it's a
            # soft judgment call and tool_choice="auto" doesn't always trigger it, which
            # left sessions stuck re-asking the same closing question instead of actually
            # closing. This check is independent of the LLM/offline path.
            if session.get("awaiting_close_confirmation"):
                await session_store.update_session(self.session_id, {"awaiting_close_confirmation": False})
                is_hi = _is_hindi(user_text)
                if _is_affirmative_text(user_text):
                    await session_store.set_state(self.session_id, "speaking")
                    await self.send_ws_event({"type": "state_change", "state": "speaking"})
                    farewell = random.choice(FAREWELL_MESSAGES_HI if is_hi else FAREWELL_MESSAGES_EN)
                    await self._stream_spoken_response(farewell)
                    await self.send_ws_event({"type": "session_end"})
                    return
                elif _is_negative_text(user_text):
                    await session_store.set_state(self.session_id, "speaking")
                    await self.send_ws_event({"type": "state_change", "state": "speaking"})
                    reply = ("कोई बात नहीं — और किस चीज़ में मदद कर सकता हूँ?" if is_hi
                             else "No problem — what else can I help you with?")
                    await self._stream_spoken_response(reply)
                    return
                # Otherwise: not a clear yes/no — fall through and treat this as a fresh request.

            # 1. Retrieve grounded KB content from Qdrant
            kb_articles = await qdrant_manager.search_kb(user_text, limit=2)
            kb_context_str = ""
            for art in kb_articles:
                kb_context_str += f"- Title: {art['title']}\n  Steps: {'; '.join(art['steps'])}\n"

            last_turns = session.get("last_turns", [])
            
            messages = [{"role": "system", "content": SYSTEM_PROMPT.format(kb_context=kb_context_str)}]
            for turn in last_turns[-6:]:
                messages.append({"role": turn["role"], "content": turn["text"]})

            # Set state to 'speaking'
            await session_store.set_state(self.session_id, "speaking")
            await self.send_ws_event({"type": "state_change", "state": "speaking"})

            # 3. LLM Execution — streamed on the OpenAI side (text arrives as it's
            # generated rather than blocking on the whole response), but synthesized
            # as a single Rime call once the full text is known (see _stream_llm_response
            # for why per-sentence synthesis was reverted).
            if self.openai_client and settings.is_openai_live:
                try:
                    full_text, tool_call = await asyncio.wait_for(
                        self._stream_llm_response(messages),
                        timeout=20.0
                    )

                    if tool_call:
                        name, args = tool_call
                        if name == "create_ticket":
                            await session_store.set_state(self.session_id, "escalating")
                            await self.send_ws_event({"type": "state_change", "state": "escalating"})

                            tool_result = await execute_create_ticket(self.session_id, args)
                            ticket_id = tool_result["ticket"]["ticket_id"]

                            spoken_reply = f"I have escalated your issue to IT support. Ticket {ticket_id} has been opened and a technician will contact you shortly."
                            await self._stream_spoken_response(spoken_reply)
                            return

                        elif name == "end_session":
                            farewell = args.get("farewell_message") or random.choice(FAREWELL_MESSAGES)
                            await self._stream_spoken_response(farewell)
                            await self.send_ws_event({"type": "session_end"})
                            return

                    # If this reply looks like a "are you fully done?" closing question,
                    # arm the deterministic backstop above for the next turn instead of
                    # trusting the model to remember to call end_session on its own.
                    if full_text and _looks_like_closing_question(full_text):
                        await session_store.update_session(self.session_id, {"awaiting_close_confirmation": True})

                    await self._stream_spoken_response(full_text or "Let me check our IT knowledge base to assist you.")
                    return

                except Exception as e:
                    logger.error(f"OpenAI Execution Error ({e}). Using offline generator for this turn.")

            # Instant Offline Generator Mode
            spoken_reply, should_close = await self._generate_fallback_response(user_text, kb_articles)
            await self._stream_spoken_response(spoken_reply)
            if should_close:
                await self.send_ws_event({"type": "session_end"})
        except Exception as outer_e:
            logger.error(f"Error in process_user_turn: {outer_e}", exc_info=True)
            await session_store.set_state(self.session_id, "listening")
            await self.send_ws_event({"type": "state_change", "state": "listening"})

    async def _generate_fallback_response(self, user_text: str, kb_articles: List[Dict[str, Any]]) -> Tuple[str, bool]:
        user_lower = user_text.strip().lower()
        session = await session_store.get_session(self.session_id)
        current_kb_id = session.get("current_kb_id")
        current_step_idx = session.get("current_step_index", 0)
        awaiting_close = session.get("awaiting_close_confirmation", False)
        is_hi = _is_hindi(user_text)
        closing_questions = CLOSING_QUESTIONS_HI if is_hi else CLOSING_QUESTIONS_EN
        farewell_messages = FAREWELL_MESSAGES_HI if is_hi else FAREWELL_MESSAGES_EN

        is_affirmative = _is_affirmative_text(user_text)
        is_negative = _is_negative_text(user_text)

        # 0. Follow-up to a previously asked "is your work done?" closing question
        if awaiting_close:
            await session_store.update_session(self.session_id, {"awaiting_close_confirmation": False})
            if is_affirmative:
                return random.choice(farewell_messages), True
            elif is_negative:
                return ("कोई बात नहीं — और किस चीज़ में मदद कर सकता हूँ?" if is_hi
                        else "No problem — what else can I help you with?"), False
            # Otherwise fall through and treat this turn as a fresh request below.

        # 1. Escalation check
        if any(kw in user_lower for kw in [
            "ticket", "escalate", "human", "agent", "support team",
            "इंसान", "टिकट", "सपोर्ट", "एस्केलेट"
        ]):
            ticket = await execute_create_ticket(
                self.session_id,
                {
                    "issue_summary": user_text,
                    "steps_tried": ["Attempted self-serve steps"],
                    "transcript_summary": f"User requested ticket escalation: {user_text}"
                }
            )
            ticket_id = ticket["ticket"]["ticket_id"] if isinstance(ticket, dict) and "ticket" in ticket else "TICK-9901"
            await session_store.update_session(self.session_id, {"current_kb_id": None, "current_step_index": 0})
            return (f"मैंने आपके लिए एस्केलेशन टिकट {ticket_id} खोल दिया है। एक आईटी विशेषज्ञ जल्द ही आपसे संपर्क करेगा।" if is_hi
                    else f"I have opened escalation ticket {ticket_id} for you. An IT specialist will follow up shortly."), False

        # 2. Positive resolution check — ask a varied closing question rather than flatly ending
        if is_affirmative:
            await session_store.update_session(self.session_id, {
                "current_kb_id": None,
                "current_step_index": 0,
                "awaiting_close_confirmation": True
            })
            return random.choice(closing_questions), False

        # 3. Explicit Topic Keywords Detection
        TOPIC_KEYWORDS = [
            "wifi", "wi-fi", "wireless", "vpn", "password", "passcode", "mfa", "2fa",
            "authenticator", "printer", "print", "disk", "storage", "outlook", "email",
            "teams", "vdi", "citrix", "rdp", "slow", "lag", "performance"
        ]

        has_explicit_topic = any(kw in user_lower for kw in TOPIC_KEYWORDS)

        # If user explicitly specifies a topic or no active KB session exists:
        if (has_explicit_topic or not current_kb_id) and kb_articles:
            top_art = kb_articles[0]
            await session_store.update_session(self.session_id, {
                "current_kb_id": top_art["id"],
                "current_step_index": 0
            })
            first_step = top_art["steps"][0] if top_art.get("steps") else "Check your network settings."
            return f"For {top_art['title']}, let's try step 1: {first_step} Does that fix it?", False

        # 4. Step progression / negative response for active topic (e.g. "no", "nope", "didn't work")
        if is_negative and current_kb_id:
            article = mongo_store.get_kb_article(current_kb_id)
            if article and article.get("steps"):
                next_idx = current_step_idx + 1
                if next_idx < len(article["steps"]):
                    await session_store.update_session(self.session_id, {"current_step_index": next_idx})
                    next_step = article["steps"][next_idx]
                    return f"Next step for {article['title']}: {next_step} Did that resolve it?", False
                else:
                    ticket = await execute_create_ticket(
                        self.session_id,
                        {
                            "issue_summary": article["title"],
                            "steps_tried": article["steps"],
                            "transcript_summary": f"Tried all {len(article['steps'])} steps without resolution."
                        }
                    )
                    ticket_id = ticket["ticket"]["ticket_id"] if isinstance(ticket, dict) and "ticket" in ticket else "TICK-9902"
                    await session_store.update_session(self.session_id, {"current_kb_id": None, "current_step_index": 0})
                    return f"We have tried all troubleshooting steps for {article['title']} without success. I have created escalation ticket {ticket_id} for an IT specialist to assist you.", False

        # Default fallback: if mid-flow on a topic, restate the current step instead of
        # resetting to step 1 (previously caused the same reply to repeat every turn).
        if current_kb_id:
            article = mongo_store.get_kb_article(current_kb_id)
            if article and article.get("steps"):
                step = article["steps"][min(current_step_idx, len(article["steps"]) - 1)]
                return f"Let's stick with {article['title']}. Current step: {step} Did that resolve it?", False

        # No active topic yet: start with the top matched article
        if kb_articles:
            top_art = kb_articles[0]
            await session_store.update_session(self.session_id, {
                "current_kb_id": top_art["id"],
                "current_step_index": 0
            })
            first_step = top_art["steps"][0] if top_art.get("steps") else "Check your network settings."
            return f"For {top_art['title']}, let's try step 1: {first_step} Does that fix it?", False

        return "I can help walk you through troubleshooting. Could you tell me more about what device or application is giving you trouble?", False

    async def _stream_llm_response(self, messages: List[Dict[str, str]]):
        """
        Streams the chat completion (stream=True — returns text as it's generated
        rather than blocking until the entire response is done). The accumulated
        text is synthesized as a single Rime call once the stream finishes, not
        per-sentence: Rime has a large fixed per-call latency floor (~1.5-2.2s,
        nearly independent of text length — measured directly), so splitting one
        reply into several Rime calls multiplies that overhead instead of hiding
        it, making total latency worse rather than better.
        Returns (full_text, tool_call_or_none) where tool_call is (name, args) if
        the model called a tool.
        """
        stream = await self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=[CREATE_TICKET_TOOL_SPEC, END_SESSION_TOOL_SPEC],
            tool_choice="auto",
            temperature=0.4,
            stream=True
        )

        full_text = ""
        tool_call_chunks: Dict[int, Dict[str, str]] = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    entry = tool_call_chunks.setdefault(tc_delta.index, {"name": "", "arguments": ""})
                    if tc_delta.function and tc_delta.function.name:
                        entry["name"] += tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        entry["arguments"] += tc_delta.function.arguments

            if delta.content:
                full_text += delta.content

        if tool_call_chunks:
            first = next(iter(tool_call_chunks.values()))
            try:
                args = json.loads(first["arguments"]) if first["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            return full_text, (first["name"], args)

        return full_text, None

    async def _send_segment(self, text: str, index: int) -> bool:
        """
        Synthesizes and sends one spoken segment (a sentence, or a whole short
        reply). Returns False if playback was cancelled by an interruption.
        """
        current_session = await session_store.get_session(self.session_id)
        if current_session.get("state") == "interrupted":
            logger.info("Segment playback cancelled due to interruption before synthesis.")
            return False

        # Rime is the primary voice engine. It doesn't cover every language the app
        # supports, so a failed/unavailable synthesis falls back to the browser's
        # own speech synthesis on the frontend (a text-only segment, no audio attached).
        audio_bytes = await rime_tts.synthesize_speech(text)

        current_session = await session_store.get_session(self.session_id)
        if current_session.get("state") == "interrupted":
            logger.info("Segment playback cancelled due to interruption after synthesis.")
            return False

        if audio_bytes:
            await self.send_ws_event({
                "type": "tts_audio_segment",
                "index": index,
                "text_segment": text,
                "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                "mime": "audio/mp3"
            })
        else:
            await self.send_ws_event({
                "type": "tts_text_segment",
                "index": index,
                "text_segment": text
            })
        return True

    async def _end_speech_stream(self):
        await self.send_ws_event({"type": "tts_stream_end"})

    async def _stream_spoken_response(self, response_text: str):
        """Speaks one complete reply as a single segment (tool-call responses, offline fallback)."""
        await session_store.add_turn(self.session_id, "assistant", response_text)
        await self._send_segment(response_text, 0)
        await self._end_speech_stream()
