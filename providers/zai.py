import logging
import time
from zai import ZaiClient
from zai.core._errors import APIReachLimitError

from .config import ZAI_API_KEY
from .factory import AiFactory

logger = logging.getLogger(__name__)


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
        retry_delays = [10, 15, 20]

        for attempt, delay in enumerate(retry_delays, 1):
            try:
                response = self.client.chat.completions.create(
                    model="glm-4.7-flash",
                    messages=[{"role": "user", "content": message}],
                    stream=False,
                )
                return response.choices[0].message.content
            except APIReachLimitError as e:
                logger.warning(
                    f"ZAI rate limit (attempt {attempt}/{len(retry_delays)}): {e}"
                )
                if attempt < len(retry_delays):
                    time.sleep(delay)
                else:
                    return "IA com rate limit baixo"
            except Exception as e:
                logger.error(
                    f"ZAI error (attempt {attempt}/{len(retry_delays)}): {e}",
                    exc_info=True,
                )
                if attempt < len(retry_delays):
                    time.sleep(delay)
                else:
                    return "IA com rate limit baixo"

        return "IA com rate limit baixo"
