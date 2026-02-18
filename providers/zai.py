from zai import ZaiClient

from .config import ZAI_API_KEY
from .factory import AiFactory


class ZAIProvider(AiFactory):
    def __init__(self):
        self.client = ZaiClient(
            base_url="https://api.z.ai/api/coding/paas/v4", api_key=ZAI_API_KEY
        )

    def vision(self, image) -> str:
        raise NotImplementedError("vision not implemented yet")

    def transcribe_audio(self, audio_file) -> str:
        raise NotImplementedError("transcribe not implemented yet")

    def summarize(self, text) -> str:
        raise NotImplementedError("summarize not implemented yet")

    def chat(self, message) -> str:
        response = self.client.chat.completions.create(
            model="glm-4.7-flash",
            messages=[{"role": "user", "content": message}],
            stream=False,
        )
        return response.choices[0].message.content
