// Browser voice adapters for the virtual interviewer. Swap these adapters to
// use a hosted speech service without changing the interview UI or API client.
window.InterviewVoice = (() => {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  class SpeechToText {
    constructor({onTranscript, onError, onEnd} = {}) {
      this.supported = Boolean(Recognition);
      this.onTranscript = onTranscript || (() => {});
      this.onError = onError || (() => {});
      this.onEnd = onEnd || (() => {});
      this.recognition = null;
      this.listening = false;
      this.finalText = '';
      if (!this.supported) return;
      this.recognition = new Recognition();
      this.recognition.lang = 'en-US';
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const text = event.results[i][0].transcript.trim();
          if (event.results[i].isFinal && text) this.finalText += `${this.finalText ? ' ' : ''}${text}`;
          else interim += `${interim ? ' ' : ''}${text}`;
        }
        this.onTranscript({finalText: this.finalText, interimText: interim});
      };
      this.recognition.onerror = (event) => this.onError(event.error);
      this.recognition.onend = () => {
        this.listening = false;
        this.onEnd(this.finalText);
      };
    }

    start() {
      if (!this.recognition || this.listening) return false;
      this.finalText = '';
      try {
        this.recognition.start();
        this.listening = true;
        return true;
      } catch (_) {
        return false;
      }
    }

    stop() {
      if (this.recognition && this.listening) this.recognition.stop();
    }
  }

  class TextToSpeech {
    constructor({onStart, onEnd} = {}) {
      this.onStart = onStart || (() => {});
      this.onEnd = onEnd || (() => {});
      this.supported = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
    }

    speak(text) {
      if (!this.supported || !text) {
        this.onEnd();
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.96;
      utterance.onstart = this.onStart;
      utterance.onend = this.onEnd;
      utterance.onerror = this.onEnd;
      window.speechSynthesis.speak(utterance);
    }

    stop() {
      if (this.supported) window.speechSynthesis.cancel();
    }
  }

  return {SpeechToText, TextToSpeech};
})();
