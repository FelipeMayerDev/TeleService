from .factory import AiFactory
from .config import GROQ_API_KEY
from groq import Groq


class GroqProvider(AiFactory):
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.whisper_model = "whisper-large-v3"

    def chat(self, prompt):
        system = "Você é uma IA em um grupo de amigos que responde perguntas de forma clara e concisa. Responda na linguagem que for perguntado e em html"
        completion = self.client.chat.completions.create(
            model="llama-3.3-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": f"{system}"
                },
                {
                    "role": "user",
                    "content": f"{prompt}"
                }
            ],
            temperature=1,
            top_p=1,
            stream=False,
        )
        return completion.choices[0].message.content

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