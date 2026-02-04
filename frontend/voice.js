/**
 * Voice System for A320 Checklist Companion
 * Handles PTT (keyboard + gamepad), audio playback, and speech recognition.
 */

class VoiceSystem {
    constructor(app) {
        this.app = app;
        this.ws = null;

        // State
        this.enabled = false;
        this.isListening = false;
        this.whisperAvailable = false;
        this.useWhisper = true;

        // PTT settings
        this.pttKey = 'Space';
        this.pttGamepadButton = null;
        this.pttPressed = false;

        // Audio
        this.audioQueue = [];
        this.isPlayingAudio = false;
        this.currentAudio = null;

        // Web Speech API
        this.speechSynthesis = window.speechSynthesis;
        this.speechRecognition = null;
        this.webSpeechAvailable = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;

        // MediaRecorder for Whisper
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.mediaStream = null;

        // Gamepad
        this.gamepadIndex = null;
        this.gamepadPollInterval = null;
        this.lastGamepadButtonState = false;

        // UI Elements
        this.pttIndicator = null;
        this.transcriptionDisplay = null;

        this.init();
    }

    init() {
        this.setupUI();
        this.setupKeyboardPTT();
        this.setupGamepadDetection();
        this.setupWebSpeechRecognition();
    }

    setWebSocket(ws) {
        this.ws = ws;
    }

    // ================================
    // UI Setup
    // ================================

    setupUI() {
        // Create PTT indicator overlay
        this.pttIndicator = document.createElement('div');
        this.pttIndicator.className = 'voice-ptt-indicator hidden';
        this.pttIndicator.innerHTML = `
            <div class="ptt-mic-icon">&#127908;</div>
            <div class="ptt-text">LISTENING...</div>
            <div class="ptt-hint">Release to send</div>
        `;
        document.body.appendChild(this.pttIndicator);

        // Create transcription result display
        this.transcriptionDisplay = document.createElement('div');
        this.transcriptionDisplay.className = 'voice-transcription hidden';
        document.body.appendChild(this.transcriptionDisplay);
    }

    showPTTIndicator() {
        this.pttIndicator.classList.remove('hidden');
        this.pttIndicator.classList.add('active');
    }

    hidePTTIndicator() {
        this.pttIndicator.classList.remove('active');
        this.pttIndicator.classList.add('hidden');
    }

    showTranscription(text, accepted) {
        this.transcriptionDisplay.textContent = text;
        this.transcriptionDisplay.className = 'voice-transcription ' + (accepted ? 'accepted' : 'rejected');

        // Hide after a delay
        setTimeout(() => {
            this.transcriptionDisplay.classList.add('hidden');
        }, 2000);
    }

    // ================================
    // Keyboard PTT
    // ================================

    setupKeyboardPTT() {
        document.addEventListener('keydown', (e) => {
            if (!this.enabled) return;
            if (e.code === this.pttKey && !e.repeat && !this.pttPressed) {
                e.preventDefault();
                this.startPTT();
            }
        });

        document.addEventListener('keyup', (e) => {
            if (!this.enabled) return;
            if (e.code === this.pttKey && this.pttPressed) {
                e.preventDefault();
                this.stopPTT();
            }
        });
    }

    // ================================
    // Gamepad PTT
    // ================================

    setupGamepadDetection() {
        window.addEventListener('gamepadconnected', (e) => {
            console.log('Gamepad connected:', e.gamepad.id);
            this.gamepadIndex = e.gamepad.index;
            this.startGamepadPolling();
        });

        window.addEventListener('gamepaddisconnected', (e) => {
            console.log('Gamepad disconnected');
            if (this.gamepadIndex === e.gamepad.index) {
                this.gamepadIndex = null;
                this.stopGamepadPolling();
            }
        });

        // Check for already connected gamepads
        const gamepads = navigator.getGamepads();
        for (const gamepad of gamepads) {
            if (gamepad) {
                this.gamepadIndex = gamepad.index;
                this.startGamepadPolling();
                break;
            }
        }
    }

    startGamepadPolling() {
        if (this.gamepadPollInterval) return;

        this.gamepadPollInterval = setInterval(() => {
            this.pollGamepad();
        }, 50); // 20Hz polling
    }

    stopGamepadPolling() {
        if (this.gamepadPollInterval) {
            clearInterval(this.gamepadPollInterval);
            this.gamepadPollInterval = null;
        }
    }

    pollGamepad() {
        if (!this.enabled || this.pttGamepadButton === null || this.gamepadIndex === null) return;

        const gamepads = navigator.getGamepads();
        const gamepad = gamepads[this.gamepadIndex];
        if (!gamepad) return;

        const buttonState = gamepad.buttons[this.pttGamepadButton]?.pressed || false;

        // Detect press
        if (buttonState && !this.lastGamepadButtonState && !this.pttPressed) {
            this.startPTT();
        }
        // Detect release
        else if (!buttonState && this.lastGamepadButtonState && this.pttPressed) {
            this.stopPTT();
        }

        this.lastGamepadButtonState = buttonState;
    }

    getConnectedGamepads() {
        const result = [];
        const gamepads = navigator.getGamepads();
        for (const gamepad of gamepads) {
            if (gamepad) {
                result.push({
                    index: gamepad.index,
                    id: gamepad.id,
                    buttons: gamepad.buttons.length,
                    axes: gamepad.axes.length,
                });
            }
        }
        return result;
    }

    // ================================
    // PTT Control
    // ================================

    async startPTT() {
        if (this.pttPressed || this.isListening) return;

        this.pttPressed = true;
        this.isListening = true;
        this.showPTTIndicator();

        // Notify backend
        this.sendVoiceCommand('voice_start_listening', {});

        // Start recording for Whisper if available
        if (this.useWhisper && this.whisperAvailable) {
            await this.startRecording();
        } else if (this.webSpeechAvailable) {
            this.startWebSpeechRecognition();
        }
    }

    async stopPTT() {
        if (!this.pttPressed) return;

        this.pttPressed = false;
        this.isListening = false;
        this.hidePTTIndicator();

        // Stop recording and send to backend
        if (this.useWhisper && this.whisperAvailable && this.mediaRecorder) {
            const audioBlob = await this.stopRecording();
            if (audioBlob) {
                await this.sendAudioToBackend(audioBlob);
            }
        } else if (this.webSpeechAvailable && this.speechRecognition) {
            this.speechRecognition.stop();
        } else {
            // Just notify backend we stopped
            this.sendVoiceCommand('voice_stop_listening', {});
        }
    }

    // ================================
    // Media Recording (for Whisper)
    // ================================

    async startRecording() {
        try {
            if (!this.mediaStream) {
                this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            }

            this.audioChunks = [];
            this.mediaRecorder = new MediaRecorder(this.mediaStream, {
                mimeType: 'audio/webm;codecs=opus'
            });

            this.mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    this.audioChunks.push(e.data);
                }
            };

            this.mediaRecorder.start();
            console.log('Recording started');
        } catch (err) {
            console.error('Failed to start recording:', err);
            // Fall back to Web Speech API
            if (this.webSpeechAvailable) {
                this.startWebSpeechRecognition();
            }
        }
    }

    stopRecording() {
        return new Promise((resolve) => {
            if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
                resolve(null);
                return;
            }

            this.mediaRecorder.onstop = () => {
                const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
                console.log('Recording stopped, blob size:', blob.size);
                resolve(blob);
            };

            this.mediaRecorder.stop();
        });
    }

    async sendAudioToBackend(audioBlob) {
        try {
            // Convert blob to base64
            const reader = new FileReader();
            const base64Promise = new Promise((resolve) => {
                reader.onloadend = () => {
                    const base64 = reader.result.split(',')[1];
                    resolve(base64);
                };
            });
            reader.readAsDataURL(audioBlob);
            const base64Audio = await base64Promise;

            this.sendVoiceCommand('voice_stop_listening', {
                audio_data: base64Audio,
            });
        } catch (err) {
            console.error('Failed to send audio:', err);
        }
    }

    // ================================
    // Web Speech API Recognition
    // ================================

    setupWebSpeechRecognition() {
        if (!this.webSpeechAvailable) return;

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.speechRecognition = new SpeechRecognition();
        this.speechRecognition.continuous = false;
        this.speechRecognition.interimResults = false;
        this.speechRecognition.lang = 'en-US';

        this.speechRecognition.onresult = (e) => {
            const transcript = e.results[0][0].transcript;
            console.log('Web Speech result:', transcript);
            this.sendVoiceCommand('voice_web_speech_result', {
                text: transcript,
                confidence: e.results[0][0].confidence,
            });
        };

        this.speechRecognition.onerror = (e) => {
            console.error('Web Speech error:', e.error);
            if (e.error !== 'aborted') {
                this.sendVoiceCommand('voice_stop_listening', {});
            }
        };

        this.speechRecognition.onend = () => {
            console.log('Web Speech ended');
        };
    }

    startWebSpeechRecognition() {
        if (this.speechRecognition) {
            try {
                this.speechRecognition.start();
                console.log('Web Speech recognition started');
            } catch (err) {
                console.error('Failed to start Web Speech:', err);
            }
        }
    }

    // ================================
    // Audio Playback (TTS)
    // ================================

    async playAudioSequence(sequence, settings = {}) {
        for (const item of sequence) {
            await this.playSpeechItem(item, settings);
        }
    }

    playSpeechItem(item, settings = {}) {
        return new Promise((resolve) => {
            if (item.type === 'audio') {
                // Play audio file
                this.playAudioFile(item.url, settings.volume || 1.0)
                    .then(resolve)
                    .catch(() => {
                        // Fall back to TTS if audio fails
                        this.speakText(item.text || item.key, settings.rate || 1.0, settings.volume || 1.0)
                            .then(resolve);
                    });
            } else if (item.type === 'tts') {
                // Use Web Speech API TTS
                this.speakText(item.text, settings.rate || 1.0, settings.volume || 1.0)
                    .then(resolve);
            } else {
                resolve();
            }
        });
    }

    playAudioFile(url, volume = 1.0) {
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
            audio.volume = volume;

            audio.onended = () => {
                this.currentAudio = null;
                resolve();
            };

            audio.onerror = (err) => {
                console.error('Audio playback error:', err);
                this.currentAudio = null;
                reject(err);
            };

            this.currentAudio = audio;
            audio.play().catch(reject);
        });
    }

    speakText(text, rate = 1.0, volume = 1.0) {
        return new Promise((resolve) => {
            if (!this.speechSynthesis) {
                resolve();
                return;
            }

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = rate;
            utterance.volume = volume;
            utterance.lang = 'en-US';

            utterance.onend = () => resolve();
            utterance.onerror = () => resolve();

            this.speechSynthesis.speak(utterance);
        });
    }

    stopAudio() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        if (this.speechSynthesis) {
            this.speechSynthesis.cancel();
        }
    }

    // ================================
    // WebSocket Communication
    // ================================

    sendVoiceCommand(type, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, data }));
        }
    }

    handleVoiceMessage(message) {
        switch (message.type) {
            case 'voice_speak':
                // Play speech sequence (TTS or audio files)
                this.playAudioSequence(message.data.sequence, message.data.settings);
                break;

            case 'voice_result':
                // Response from STT processing
                const { action, spoken, auto_advance, item_id } = message.data;
                const accepted = action === 'response_accepted';

                this.showTranscription(spoken || '(no transcription)', accepted);

                // Auto-advance is handled by the backend, no need to do it here
                break;

            case 'voice_listening':
                // Confirmation that backend is ready for audio
                console.log('Voice listening:', message.data);
                break;

            case 'voice_status':
                this.updateStatus(message.data);
                break;
        }
    }

    // ================================
    // Settings & Status
    // ================================

    updateSettings(settings) {
        if (settings.enabled !== undefined) this.enabled = settings.enabled;
        if (settings.ptt_keyboard_key) this.pttKey = settings.ptt_keyboard_key;
        if (settings.ptt_gamepad_button !== undefined) this.pttGamepadButton = settings.ptt_gamepad_button;
        if (settings.use_whisper !== undefined) this.useWhisper = settings.use_whisper;
    }

    updateStatus(status) {
        this.whisperAvailable = status.stt?.whisper_available || false;
        this.updateSettings(status.settings || {});
    }

    async fetchStatus() {
        try {
            const response = await fetch('/api/voice/status');
            const status = await response.json();
            this.updateStatus(status);
            return status;
        } catch (err) {
            console.error('Failed to fetch voice status:', err);
            return null;
        }
    }
}

// Export for use in app.js
window.VoiceSystem = VoiceSystem;
