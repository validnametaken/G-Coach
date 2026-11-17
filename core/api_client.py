"""
API Client - OpenAI-compatible LLM API client
"""

import re
import threading
import json
from typing import Callable, Optional

import httpx


class APIClient:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._current_request = None

    def _get_headers(self) -> dict[str, str]:
        api_config = self.config_manager.get_api_config()
        return {
            "Authorization": f"Bearer {api_config.get('api_key', '')}",
            "Content-Type": "application/json",
        }

    def _get_url(self, path: str) -> str:
        api_config = self.config_manager.get_api_config()
        base_url = api_config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        return f"{base_url}/{path.lstrip('/')}"

    @staticmethod
    def _extract_brackets(text: str) -> str:
        """Extract content within 「」; return original text if not found."""
        match = re.search(r'「(.+?)」', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def call(
        self,
        user_input: str,
        prompt_template: str,
        on_success: Callable[[str], None],
        on_error: Callable[[str], None],
        on_stream: Optional[Callable[[str], None]] = None,
    ):
        """
        Asynchronously invoke LLM API.
        
        Args:
            user_input: User input text A
            prompt_template: Prompt template B
            on_success: Success callback, taking extracted result C
            on_error: Error callback, taking error message
            on_stream: Streaming callback, taking incremental text
        """
        api_config = self.config_manager.get_api_config()

        # Build message: Prompt + instruction suffix + user input
        content = f"{prompt_template}\nPlease output only the final result enclosed in 「」\n\n{user_input}"
        messages = [
            {"role": "user", "content": content}
        ]

        # Ensure max_tokens does not exceed API limit (65536)
        max_tokens = api_config.get("max_tokens", 4096)
        if max_tokens > 65536:
            max_tokens = 65536
            print(f"[APIClient] Warning: max_tokens exceeds limit, automatically adjusted to {max_tokens}")

        def _run():
            try:
                payload = {
                    "model": api_config.get("model", "gpt-4o-mini"),
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": api_config.get("temperature", 0.7),
                }

                if on_stream:
                    # Streaming call
                    payload["stream"] = True
                    full_response = ""
                    with httpx.Client(timeout=60) as client:
                        with client.stream(
                            "POST",
                            self._get_url("chat/completions"),
                            headers=self._get_headers(),
                            json=payload,
                        ) as response:
                            response.raise_for_status()
                            for line in response.iter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                data = line[6:].strip()
                                if data == "[DONE]":
                                    break
                                parsed = json.loads(data)
                                delta = (
                                    parsed.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content")
                                )
                                if delta:
                                    full_response += delta
                                    on_stream(delta)
                    # Extract bracketed content after streaming finishes
                    final = self._extract_brackets(full_response)
                    on_success(final)
                else:
                    # Non-streaming call
                    with httpx.Client(timeout=60) as client:
                        response = client.post(
                            self._get_url("chat/completions"),
                            headers=self._get_headers(),
                            json=payload,
                        )
                        response.raise_for_status()
                        data = response.json()
                    result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    # Extract bracketed content
                    final = self._extract_brackets(result)
                    on_success(final)

            except Exception as e:
                error_msg = f"API call failed: {str(e)}"
                on_error(error_msg)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        self._current_request = thread
