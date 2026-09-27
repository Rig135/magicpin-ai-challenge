import os
import json
import logging
from typing import Dict, Any
import openai

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key and self.api_key != "test_mock":
            self.client = openai.OpenAI(api_key=self.api_key)
        else:
            self.client = None
            
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not self.client:
            # Fallback/mock for testing
            return {
                "body": "This is a mocked LLM response for testing.",
                "cta": "test_cta",
                "rationale": "Mock rationale due to missing API key."
            }
            
        try:
            response = self.client.chat.completions.create(
                model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise RuntimeError(f"LLM failure: {e}")
