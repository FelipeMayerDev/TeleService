import logging

from .factory import AiFactory
from .config import GROQ_API_KEY
from groq import Groq

logger = logging.getLogger(__name__)


class GroqProvider(AiFactory):
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.whisper_model = "whisper-large-v3"

    def chat(self, prompt):
        system = "Você é uma IA em um grupo de amigos que responde perguntas de forma clara e concisa. Responda na linguagem que for perguntado e em html"
        return self.chat_with_system(system, prompt)

    def chat_with_system(self, system_prompt, prompt):
        try:
            completion = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,
                top_p=1,
                stream=False,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return None

    def transcribe_audio(self, filename):
        try:
            with open(filename, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(filename, file.read()),
                    model=self.whisper_model,
                    response_format="verbose_json",
                )
                return transcription.text
        except Exception as e:
            pass