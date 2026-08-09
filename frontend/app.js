// VoxAssist Frontend Application Logic

let ws = null;
let isSessionActive = false;
let currentSessionId = null;
let speechRecognition = null;
let isListeningSpeech = false;
let isSpeakingAudio = false;
let lastBotSpokenText = "";
let pendingSessionEnd = false;
let mouthCloseTimer = null;

// Real Rime audio playback + waveform-driven lip sync
let ttsAudioEl = null;
let audioCtx = null;
let analyserNode = null;
let analyserData = null;
let lipSyncRAF = null;

// Playback queue for streamed speech segments (sentences arrive and get spoken
// one at a time, in order, as soon as each is ready — instead of waiting for
// the whole reply before anything plays).
let ttsQueue = [];
let ttsStreamEnded = false;
let isPlayingQueue = false;

// Custom VAD: how long to wait after the last detected speech (interim or
// final) before treating the utterance as complete, instead of relying on
// the browser's own (unmeasured, suspected slow) end-of-speech detection.
const CUSTOM_VAD_SILENCE_MS = 600;

// --- Latency test instrumentation (Test 1 & Test 3 frontend legs) ---
// Logged to console as "[latency-test]" lines; not sent anywhere, purely
// for manual measurement during a live voice session.
let _latSpeechEndAt = null;
function _latLog(label, ms) {
    console.log(`[latency-test] ${label}: ${ms.toFixed(0)}ms`);
}

// DOM Elements
const micBtn = document.getElementById('micBtn');
const micBtnText = document.getElementById('micBtnText');
const interruptBtn = document.getElementById('interruptBtn');
const ticketsBtn = document.getElementById('ticketsBtn');
const ticketsModal = document.getElementById('ticketsModal');
const closeTicketsBtn = document.getElementById('closeTicketsBtn');
const ticketsList = document.getElementById('ticketsList');

const connStatus = document.getElementById('connStatus');
const faceGlow = document.getElementById('faceGlow');
const statePill = document.getElementById('statePill');
const stateDot = document.getElementById('stateDot');
const stateLabel = document.getElementById('stateLabel');
const agentCaptionText = document.getElementById('agentCaptionText');

const leftPupil = document.getElementById('leftPupil');
const rightPupil = document.getElementById('rightPupil');
const mouthPath = document.getElementById('mouthPath');

// Colors for the status-pill badge (does not affect the robot's LEDs, which stay cyan)
const STATE_COLORS = {
    idle: '#94a3b8',
    listening: '#14b8e8',
    thinking: '#f59e0b',
    speaking: '#8b5cf6',
    interrupted: '#ef4444',
    escalating: '#eab308'
};

// Eyes are vertical LED pills — resize height (keeping them centered) to change expression.
function setEyeHeight(height) {
    leftPupil.setAttribute('height', height);
    leftPupil.setAttribute('y', -height / 2);
    rightPupil.setAttribute('height', height);
    rightPupil.setAttribute('y', -height / 2);
}

// Mouth is a horizontal LED pill — resize width/height (keeping it centered) to change shape.
function setMouthPill(width, height) {
    mouthPath.setAttribute('width', width);
    mouthPath.setAttribute('height', height);
    mouthPath.setAttribute('x', -width / 2);
    mouthPath.setAttribute('y', -height / 2);
    mouthPath.setAttribute('rx', height / 2);
}

// Per-state resting expression: eye pill height + closed-mouth pill size.
// Continuous pulsing/breathing/tilt animation is handled declaratively in CSS via the state class.
const EXPRESSIONS = {
    idle: { eyeHeight: 30, mouthWidth: 34, mouthHeight: 10 },
    listening: { eyeHeight: 36, mouthWidth: 30, mouthHeight: 9 },
    thinking: { eyeHeight: 24, mouthWidth: 26, mouthHeight: 8 },
    speaking: { eyeHeight: 30, mouthWidth: 30, mouthHeight: 10 },
    interrupted: { eyeHeight: 40, mouthWidth: 20, mouthHeight: 8 },
    escalating: { eyeHeight: 30, mouthWidth: 30, mouthHeight: 10 }
};

function applyExpression(state) {
    const expr = EXPRESSIONS[state] || EXPRESSIONS.idle;
    setEyeHeight(expr.eyeHeight);
    setMouthPill(expr.mouthWidth, expr.mouthHeight);
}

// Multi-language support — no manual toggle. Language is auto-detected from text
// (Unicode script for non-Latin languages) and the speech recognizer / TTS voice
// silently follow whichever language the conversation is currently in.
let conversationLang = 'en-US';

const SCRIPT_LANG_RANGES = [
    { lang: 'hi-IN', re: /[ऀ-ॿ]/ },  // Devanagari (Hindi, Marathi, ...)
    { lang: 'bn-IN', re: /[ঀ-৿]/ },  // Bengali
    { lang: 'ta-IN', re: /[஀-௿]/ },  // Tamil
    { lang: 'te-IN', re: /[ఀ-౿]/ },  // Telugu
    { lang: 'ar-SA', re: /[؀-ۿ]/ },  // Arabic
    { lang: 'he-IL', re: /[֐-׿]/ },  // Hebrew
    { lang: 'ru-RU', re: /[Ѐ-ӿ]/ },  // Cyrillic (Russian, ...)
    { lang: 'el-GR', re: /[Ͱ-Ͽ]/ },  // Greek
    { lang: 'th-TH', re: /[฀-๿]/ },  // Thai
    { lang: 'zh-CN', re: /[一-鿿]/ },  // CJK Unified (Chinese)
    { lang: 'ja-JP', re: /[぀-ヿ]/ },  // Hiragana / Katakana (Japanese)
    { lang: 'ko-KR', re: /[가-힯]/ }   // Hangul (Korean)
];

// Latin-script languages (Spanish, French, German, ...) can't be told apart from
// English by character set alone — they default to English recognition/voice.
function detectTextLang(text) {
    for (const { lang, re } of SCRIPT_LANG_RANGES) {
        if (re.test(text)) return lang;
    }
    return 'en-US';
}

// Preferred named voices per language (falls back to any matching-language voice if absent)
const PREFERRED_VOICE_NAMES = {
    'en-US': ['Google UK English Female', 'Google US English', 'Microsoft Zira', 'Microsoft Hazel', 'Microsoft Aria', 'Microsoft Jenny', 'Samantha', 'Victoria', 'Karen', 'Moira', 'Tessa'],
    'hi-IN': ['Google हिन्दी', 'Microsoft Swara', 'Microsoft Kalpana', 'Microsoft Heera', 'Lekha']
};

let voiceCache = {};

function resetVoiceCache() {
    voiceCache = {};
}

function pickVoiceForLang(lang) {
    if (lang in voiceCache) return voiceCache[lang];
    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return null;

    const langPrefix = lang.split('-')[0].toLowerCase();
    let match = null;

    for (const name of (PREFERRED_VOICE_NAMES[lang] || [])) {
        match = voices.find(v => v.name.includes(name));
        if (match) break;
    }
    if (!match) match = voices.find(v => v.lang.toLowerCase() === lang.toLowerCase() && /female/i.test(v.name));
    if (!match) match = voices.find(v => v.lang.toLowerCase().startsWith(langPrefix) && /female/i.test(v.name));
    if (!match) match = voices.find(v => v.lang.toLowerCase().startsWith(langPrefix));

    voiceCache[lang] = match || null;
    return voiceCache[lang];
}

if ('speechSynthesis' in window) {
    resetVoiceCache();
    window.speechSynthesis.onvoiceschanged = resetVoiceCache;
}

// Words to ignore from microphone speaker feedback
const GREETING_BLACK_LIST = [
    "voxassist", "helpdesk agent", "running into today", "hi alex",
    "what issue are you", "what issue", "running into", "helpdesk"
];

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    initEvents();
    initSpeechRecognition();
    startEyeBlinkLoop();
    startMouseEyeTracking();
    initNetworkBackground();
});

// Animated "network" background — slow-drifting nodes connected by lines that
// fade with distance, rendered on a full-viewport canvas behind everything.
function initNetworkBackground() {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const LINK_DIST = 150;
    const MAX_PARTICLES = 180;
    let width, height, particles, rafId;

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }

    function createParticles() {
        const count = Math.min(MAX_PARTICLES, Math.floor((width * height) / 13000));
        particles = [];
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.25,
                vy: (Math.random() - 0.5) * 0.25
            });
        }
    }

    function step() {
        ctx.clearRect(0, 0, width, height);

        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x <= 0 || p.x >= width) p.vx *= -1;
            if (p.y <= 0 || p.y >= height) p.vy *= -1;
        }

        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const a = particles[i], b = particles[j];
                const dx = a.x - b.x, dy = a.y - b.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < LINK_DIST) {
                    const alpha = (1 - dist / LINK_DIST) * 0.45;
                    ctx.strokeStyle = `rgba(90, 120, 160, ${alpha})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            }
        }

        for (const p of particles) {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(80, 110, 150, 0.65)';
            ctx.fill();
        }

        rafId = requestAnimationFrame(step);
    }

    resize();
    createParticles();
    step();

    let resizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            cancelAnimationFrame(rafId);
            resize();
            createParticles();
            step();
        }, 200);
    });
}

function initEvents() {
    micBtn.addEventListener('click', toggleSession);
    interruptBtn.addEventListener('click', triggerBargeIn);
    ticketsBtn.addEventListener('click', loadAndShowTickets);
    closeTicketsBtn.addEventListener('click', () => ticketsModal.hidden = true);
}

// WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/voxassist`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        connStatus.classList.add('connected');
        connStatus.querySelector('.status-text').textContent = 'Connected';
        isSessionActive = true;
        pendingSessionEnd = false;
        micBtn.classList.add('active');
        micBtnText.textContent = 'End Session';
        interruptBtn.disabled = false;
        startKeepAliveWatchdog();
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
    };

    ws.onclose = () => {
        connStatus.classList.remove('connected');
        connStatus.querySelector('.status-text').textContent = 'Disconnected';
        isSessionActive = false;
        micBtn.classList.remove('active');
        micBtnText.textContent = 'Start Session';
        interruptBtn.disabled = true;
        updateState('idle');
        stopKeepAliveWatchdog();
        stopSpeechListening();
        window.speechSynthesis.cancel();
        stopRimeAudio();
        resetTtsQueue();
    };

    ws.onerror = (error) => {
        console.error('WebSocket Error:', error);
    };
}

function toggleSession() {
    if (isSessionActive) {
        if (ws) ws.close();
    } else {
        connectWebSocket();
    }
}

// Runs after the agent finishes speaking a normal (non-greeting) turn — either
// closes the session if one was pending, or goes back to listening.
function onAgentSpeechComplete() {
    if (pendingSessionEnd) {
        pendingSessionEnd = false;
        agentCaptionText.textContent = 'Session ended. Tap Start Session to begin again.';
        updateState('idle');
        if (ws) ws.close();
        return;
    }
    updateState('listening');
    setTimeout(() => startSpeechListening(), 800);
}

function resetTtsQueue() {
    ttsQueue = [];
    ttsStreamEnded = false;
    isPlayingQueue = false;
}

// Queues one spoken segment (a sentence, or a whole short reply) and starts
// playback if nothing is currently playing.
function enqueueTtsSegment(text, audioBase64, mime) {
    ttsQueue.push({ text, audioBase64, mime });
    if (!isPlayingQueue) {
        playNextInQueue();
    }
}

// Plays segments one at a time, in order. Once the queue is empty and no more
// segments are coming (tts_stream_end already received), the turn is complete.
function playNextInQueue() {
    if (ttsQueue.length === 0) {
        isPlayingQueue = false;
        if (ttsStreamEnded) {
            onAgentSpeechComplete();
        }
        return;
    }

    isPlayingQueue = true;
    const segment = ttsQueue.shift();
    lastBotSpokenText = segment.text.toLowerCase();
    agentCaptionText.textContent = segment.text;
    conversationLang = detectTextLang(segment.text);
    updateState('speaking');

    if (segment.audioBase64) {
        playRimeAudio(segment.audioBase64, segment.mime, playNextInQueue);
    } else {
        // Rime unavailable/failed for this segment — fall back to the browser's voice.
        speakBrowserUtterance(segment.text, playNextInQueue);
    }
}

// Handle Incoming Server Events
function handleServerEvent(event) {
    switch (event.type) {
        case 'connected':
            currentSessionId = event.session_id;
            lastBotSpokenText = event.greeting.toLowerCase();
            conversationLang = detectTextLang(event.greeting);
            updateState('speaking');
            agentCaptionText.textContent = event.greeting;
            if (event.audio_base64) {
                playRimeAudio(event.audio_base64, event.mime, () => {
                    updateState('listening');
                    setTimeout(() => startSpeechListening(), 1000);
                });
            } else {
                speakBrowserUtterance(event.greeting, () => {
                    updateState('listening');
                    setTimeout(() => startSpeechListening(), 1000);
                });
            }
            break;

        // A spoken segment (one sentence, or a whole short reply) is ready — real
        // Rime audio if synthesis succeeded, text-only (browser voice fallback)
        // otherwise. Segments are queued and played back-to-back in order, so the
        // agent can start speaking the first sentence while later ones are still
        // being generated/synthesized.
        case 'tts_audio_segment':
            console.log('[latency-test] WS audio segment received at', performance.now().toFixed(0));
            enqueueTtsSegment(event.text_segment, event.audio_base64, event.mime);
            break;

        case 'tts_text_segment':
            enqueueTtsSegment(event.text_segment, null, null);
            break;

        // No more segments coming for this turn — completion fires once the
        // queue finishes draining (it may still be playing queued segments).
        case 'tts_stream_end':
            ttsStreamEnded = true;
            if (!isPlayingQueue && ttsQueue.length === 0) {
                onAgentSpeechComplete();
            }
            break;

        case 'session_end':
            pendingSessionEnd = true;
            break;

        case 'state_change':
            updateState(event.state);
            if (event.state === 'thinking') {
                resetTtsQueue();
            }
            if (event.state === 'listening' && !isSpeakingAudio) {
                setTimeout(() => startSpeechListening(), 500);
            }
            break;

        case 'pong':
            break;
    }
}

// Update Robot Face Visual State
function updateState(state) {
    faceGlow.className = `face-glow-container ${state}`;
    applyExpression(state);

    const color = STATE_COLORS[state] || STATE_COLORS.idle;
    stateDot.style.backgroundColor = color;
    stateDot.style.boxShadow = `0 0 10px ${color}`;
    stateLabel.textContent = `Session ${state.toUpperCase()}`;

    if (state === 'speaking') {
        isSpeakingAudio = true;
    } else if (state !== 'thinking') {
        isSpeakingAudio = false;
    }

    if (state === 'interrupted') {
        agentCaptionText.textContent = '⚡ Interrupted! Listening for your response...';
        triggerBargeInVisuals();
    } else if (state === 'escalating') {
        agentCaptionText.textContent = 'Opening an IT Support Escalation Ticket...';
    }
}

// Mid-Sentence Interruption (Barge-In)
function triggerBargeIn() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'barge_in' }));
        window.speechSynthesis.cancel();
        stopRimeAudio();
        resetTtsQueue();
        isSpeakingAudio = false;
        updateState('interrupted');
        setTimeout(() => startSpeechListening(), 500);
    }
}

// Brief "snap wide" eye flash on interruption, then settle back to listening size
function triggerBargeInVisuals() {
    setEyeHeight(44);
    setTimeout(() => {
        setEyeHeight(EXPRESSIONS.listening.eyeHeight);
    }, 350);
}

// Lip Sync Audio Amplitude Animation — the mouth LED pill morphs width/height with voice amplitude
function animateLipSync(amplitude) {
    const width = 22 + amplitude * 20;
    const height = 8 + amplitude * 22;
    setMouthPill(width, height);
}

// Web Speech API Integration, with a custom VAD layered on top: the browser's
// own end-of-speech detection (onspeechend -> final result) is a black box
// with no configurable timeout and is suspected to be a major contributor to
// total turn latency. Rather than waiting for it, interim results are used to
// detect a CUSTOM_VAD_SILENCE_MS pause in speech ourselves and send as soon
// as that fires — falling back to the browser's own final result if it
// happens to arrive first.
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        speechRecognition = new SpeechRecognition();
        speechRecognition.continuous = true;
        speechRecognition.interimResults = true;

        let silenceTimer = null;
        let latestTranscript = '';

        function clearSilenceTimer() {
            if (silenceTimer) {
                clearTimeout(silenceTimer);
                silenceTimer = null;
            }
        }

        function sendAndReset(source, resultAt) {
            clearSilenceTimer();
            const cleanText = latestTranscript.trim();
            latestTranscript = '';
            const lowerClean = cleanText.toLowerCase();

            // Ignore speech while agent is speaking. Threshold is deliberately low (not
            // > 2) so short-but-meaningful replies like "ok" and "no" (both exactly
            // 2 characters) actually get sent instead of being silently dropped.
            if (cleanText.length > 1 && !isSpeakingAudio) {
                if (GREETING_BLACK_LIST.some(phrase => lowerClean.includes(phrase))) {
                    console.log('Ignored greeting echo feedback:', cleanText);
                } else if (lastBotSpokenText && lowerClean.includes(lastBotSpokenText.slice(-15))) {
                    console.log('Ignored speaker echo feedback:', cleanText);
                } else if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'user_speech', text: cleanText }));
                    const sendAt = performance.now(); // Test 1 point C: WS message sent
                    if (_latSpeechEndAt != null) {
                        _latLog(`B - A (speechend -> ${source})`, resultAt - _latSpeechEndAt);
                        _latLog(`C - A (speechend -> ws.send, via ${source})`, sendAt - _latSpeechEndAt);
                    } else {
                        console.log(`[latency-test] sent via ${source} (no onspeechend observed first)`);
                    }
                }
            }

            // Cut off the recognizer's own pending finalization for this
            // utterance so it can't fire a duplicate/late onresult later —
            // abort() (unlike stop()) does not produce a trailing final result.
            try { speechRecognition.abort(); } catch (e) {}
        }

        // Test 1 instrumentation, point A: the browser's own internal signal
        // that it believes the user has stopped talking — kept so the custom
        // VAD above can be compared against it directly during live testing.
        speechRecognition.onspeechend = () => {
            _latSpeechEndAt = performance.now();
            console.log('[latency-test] A (onspeechend) at', _latSpeechEndAt.toFixed(0));
        };

        speechRecognition.onresult = (event) => {
            const resultAt = performance.now();
            let combined = '';
            let sawFinal = false;
            for (let i = event.resultIndex; i < event.results.length; i++) {
                combined += event.results[i][0].transcript;
                if (event.results[i].isFinal) sawFinal = true;
            }
            if (!combined) return;
            latestTranscript = combined;

            clearSilenceTimer();
            if (sawFinal) {
                // Browser finished before our custom timer did — use its result immediately.
                sendAndReset('browser-final', resultAt);
            } else {
                // Custom VAD: if no further speech arrives within the window,
                // treat the utterance as complete instead of waiting on the
                // browser's own (potentially much slower) endpointing.
                silenceTimer = setTimeout(() => sendAndReset('silence-timeout', performance.now()), CUSTOM_VAD_SILENCE_MS);
            }
        };

        let watchdogCheckInterval = null;

        speechRecognition.onend = () => {
            clearSilenceTimer();
            isListeningSpeech = false;
            if (isSessionActive) {
                if (!isSpeakingAudio) {
                    setTimeout(() => startSpeechListening(), 300);
                } else {
                    // If recognizer ended while agent was speaking, poll until speaking finishes
                    if (watchdogCheckInterval) clearInterval(watchdogCheckInterval);
                    watchdogCheckInterval = setInterval(() => {
                        if (!isSessionActive) {
                            clearInterval(watchdogCheckInterval);
                        } else if (!isSpeakingAudio) {
                            clearInterval(watchdogCheckInterval);
                            startSpeechListening();
                        }
                    }, 400);
                }
            }
        };

        speechRecognition.onerror = (e) => {
            clearSilenceTimer();
            console.warn('Speech Recognition Warning:', e.error);
            isListeningSpeech = false;
            if (isSessionActive && e.error !== 'aborted') {
                setTimeout(() => startSpeechListening(), 800);
            }
        };
    }
}

let keepAliveWatchdogTimer = null;

function startKeepAliveWatchdog() {
    stopKeepAliveWatchdog();
    keepAliveWatchdogTimer = setInterval(() => {
        if (isSessionActive && !isSpeakingAudio && !isListeningSpeech) {
            console.log('[VAD Watchdog] Speech recognition inactive during session — restarting...');
            startSpeechListening();
        }
    }, 2000);
}

function stopKeepAliveWatchdog() {
    if (keepAliveWatchdogTimer) {
        clearInterval(keepAliveWatchdogTimer);
        keepAliveWatchdogTimer = null;
    }
}

function startSpeechListening() {
    if (speechRecognition && !isListeningSpeech && !isSpeakingAudio) {
        try {
            speechRecognition.lang = conversationLang;
            speechRecognition.start();
            isListeningSpeech = true;
        } catch (e) {
            if (e.name === 'InvalidStateError') {
                isListeningSpeech = true;
            } else {
                console.warn('startSpeechListening error:', e);
                isListeningSpeech = false;
            }
        }
    }
}

function stopSpeechListening() {
    if (speechRecognition && isListeningSpeech) {
        try {
            speechRecognition.stop();
            isListeningSpeech = false;
        } catch (e) {
            isListeningSpeech = false;
        }
    }
}

// Real Rime Audio Playback — plays actual synthesized audio from the backend and
// drives lip sync from the real waveform via the Web Audio API, instead of guessing.
function ensureAudioGraph() {
    if (ttsAudioEl) return;
    ttsAudioEl = new Audio();
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaElementSource(ttsAudioEl);
    analyserNode = audioCtx.createAnalyser();
    // Time-domain (waveform) data gives true loudness via RMS — frequency-bin
    // averaging was diluted by high frequencies that carry little speech energy,
    // making the mouth respond weakly and out of step with the actual audio.
    analyserNode.fftSize = 1024;
    analyserData = new Uint8Array(analyserNode.fftSize);
    source.connect(analyserNode);
    analyserNode.connect(audioCtx.destination);
}

// Exponential smoothing keeps the mouth from flickering frame-to-frame while
// staying responsive enough to track syllables in real time.
let smoothedAmplitude = 0;

function stopRimeAudio() {
    cancelAnimationFrame(lipSyncRAF);
    if (ttsAudioEl && !ttsAudioEl.paused) {
        ttsAudioEl.pause();
    }
    smoothedAmplitude = 0;
    animateLipSync(0);
}

function tickLipSync() {
    analyserNode.getByteTimeDomainData(analyserData);

    let sumSquares = 0;
    for (let i = 0; i < analyserData.length; i++) {
        const sample = (analyserData[i] - 128) / 128; // -1..1
        sumSquares += sample * sample;
    }
    const rms = Math.sqrt(sumSquares / analyserData.length);
    // Speech RMS typically sits well under 1.0 even at full volume — scale up
    // so quiet consonants and loud vowels both produce visible mouth movement.
    const targetAmplitude = Math.min(1, rms * 3.5);

    smoothedAmplitude += (targetAmplitude - smoothedAmplitude) * 0.6;
    if (smoothedAmplitude < 0.03) smoothedAmplitude = 0;

    animateLipSync(smoothedAmplitude);
    lipSyncRAF = requestAnimationFrame(tickLipSync);
}

function playRimeAudio(base64Audio, mimeType, onCompleteCallback) {
    ensureAudioGraph();
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }

    stopSpeechListening();
    isSpeakingAudio = true;

    const byteArray = Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0));
    const blob = new Blob([byteArray], { type: mimeType || 'audio/mp3' });
    const url = URL.createObjectURL(blob);

    const cleanup = () => {
        cancelAnimationFrame(lipSyncRAF);
        animateLipSync(0);
        URL.revokeObjectURL(url);
        isSpeakingAudio = false;
    };

    ttsAudioEl.onended = () => {
        cleanup();
        if (onCompleteCallback) onCompleteCallback();
    };
    ttsAudioEl.onerror = () => {
        cleanup();
        if (onCompleteCallback) onCompleteCallback();
    };

    ttsAudioEl.src = url;
    const _latPlayCalledAt = performance.now();
    console.log('[latency-test] audio element ready, play() called at', _latPlayCalledAt.toFixed(0));
    ttsAudioEl.play().then(() => {
        const playingAt = performance.now();
        _latLog('play() called -> playback actually started', playingAt - _latPlayCalledAt);
        tickLipSync();
    }).catch((e) => {
        console.warn('Rime audio playback failed:', e);
        cleanup();
        if (onCompleteCallback) onCompleteCallback();
    });
}

// Browser Speech Synthesis for Spoken Voice Output
function speakBrowserUtterance(text, onCompleteCallback) {
    if ('speechSynthesis' in window) {
        stopSpeechListening();
        isSpeakingAudio = true;
        window.speechSynthesis.cancel();
        
        const detectedLang = detectTextLang(text);
        conversationLang = detectedLang; // primes the recognizer for the user's next turn

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = detectedLang;
        utterance.rate = detectedLang === 'en-US' ? 1.05 : 0.95;
        utterance.pitch = 1.15;
        const voice = pickVoiceForLang(detectedLang);
        if (voice) {
            utterance.voice = voice;
        }

        utterance.onboundary = (e) => {
            if (e.name === 'word') {
                clearTimeout(mouthCloseTimer);
                // Browsers don't expose real audio data for their built-in voices, so
                // this can't be true waveform sync — but scaling both the open size and
                // hold duration by the actual word's length (from the browser's own
                // boundary event) tracks real speech rhythm far better than a fixed
                // duration with a random size.
                const wordLen = e.charLength || 4;
                const amplitude = Math.min(1, 0.5 + wordLen * 0.035 + Math.random() * 0.1);
                const openDuration = Math.min(220, 70 + wordLen * 12);
                animateLipSync(amplitude);
                mouthCloseTimer = setTimeout(() => animateLipSync(0.05), openDuration);
            }
        };

        utterance.onend = () => {
            clearTimeout(mouthCloseTimer);
            animateLipSync(0);
            isSpeakingAudio = false;
            if (onCompleteCallback) onCompleteCallback();
        };

        utterance.onerror = () => {
            clearTimeout(mouthCloseTimer);
            animateLipSync(0);
            isSpeakingAudio = false;
            if (onCompleteCallback) onCompleteCallback();
        };

        window.speechSynthesis.speak(utterance);
    } else {
        if (onCompleteCallback) onCompleteCallback();
    }
}

// Eye Blink & Mouse Tracking Animations
function startEyeBlinkLoop() {
    setInterval(() => {
        if (Math.random() > 0.3) {
            leftPupil.style.transform = 'scaleY(0.1)';
            rightPupil.style.transform = 'scaleY(0.1)';
            setTimeout(() => {
                leftPupil.style.transform = 'scaleY(1)';
                rightPupil.style.transform = 'scaleY(1)';
            }, 80);
        }
    }, 4000);
}

function startMouseEyeTracking() {
    document.addEventListener('mousemove', (e) => {
        const mouseX = e.clientX / window.innerWidth - 0.5;
        const mouseY = e.clientY / window.innerHeight - 0.5;
        
        leftPupil.style.transform = `translate(${mouseX * 12}px, ${mouseY * 12}px)`;
        rightPupil.style.transform = `translate(${mouseX * 12}px, ${mouseY * 12}px)`;
    });
}

// Load Escalation Tickets Modal
async function loadAndShowTickets() {
    try {
        const res = await fetch('/api/tickets');
        const data = await res.json();
        
        if (data.tickets && data.tickets.length > 0) {
            ticketsList.innerHTML = data.tickets.map(t => `
                <div class="ticket-item">
                    <h4>Ticket ID: ${t.ticket_id} (${t.status.toUpperCase()})</h4>
                    <p><strong>Summary:</strong> ${t.issue_summary}</p>
                    <p><strong>Steps Attempted:</strong> ${t.steps_tried ? t.steps_tried.join(', ') : 'None'}</p>
                    <p><small>Created: ${new Date(t.created_at).toLocaleString()}</small></p>
                </div>
            `).join('');
        } else {
            ticketsList.innerHTML = '<p class="empty-state">No tickets escalated yet.</p>';
        }
    } catch (e) {
        ticketsList.innerHTML = '<p class="empty-state">Unable to load tickets.</p>';
    }
    
    ticketsModal.hidden = false;
}
