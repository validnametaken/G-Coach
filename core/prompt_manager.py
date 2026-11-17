"""
Prompt Manager - Manages custom prompt templates
"""

import json
import uuid
from pathlib import Path
from typing import Optional


class PromptManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.prompts_file = data_dir / "prompts.json"
        self._prompts: list[dict] = []
        self._load()

    def _load(self):
        """Load prompt configuration."""
        if self.prompts_file.exists():
            try:
                with open(self.prompts_file, "r", encoding="utf-8") as f:
                    self._prompts = json.load(f)
            except Exception:
                self._prompts = []
        if not self._prompts:
            self._create_default_prompts()

    def _create_default_prompts(self):
        """Create default prompt templates."""
        self._prompts = [
            {
                "id": "default",
                "name": "General Optimization",
                "content": "Please optimize the following text to make its expression clearer and more professional while keeping the original meaning intact.",
            },
            {
                "id": "translate_en",
                "name": "Translate to English",
                "content": "Please translate the following text into natural and fluent English.",
            },
            {
                "id": "polish",
                "name": "Polish & Refine",
                "content": "Please polish the following text, fix grammar errors, enhance style to make it more elegant and fluent, while keeping the original meaning.",
            },
            {
                "id": "summarize",
                "name": "Summarize",
                "content": "Please provide a concise summary of the following content, highlighting the core points.",
            },
        ]
        self._save()

    def _save(self):
        """Save prompt configuration."""
        self.prompts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.prompts_file, "w", encoding="utf-8") as f:
            json.dump(self._prompts, f, ensure_ascii=False, indent=2)

    def get_all(self) -> list[dict]:
        """Get all prompts."""
        return self._prompts.copy()

    def get_by_id(self, prompt_id: str) -> Optional[dict]:
        """Get prompt by ID."""
        for p in self._prompts:
            if p["id"] == prompt_id:
                return p
        return None

    def add(self, name: str, content: str) -> str:
        """Add prompt, returns ID."""
        pid = str(uuid.uuid4())[:8]
        self._prompts.append({"id": pid, "name": name, "content": content})
        self._save()
        return pid

    def update(self, prompt_id: str, name: str, content: str) -> bool:
        """Update prompt."""
        for p in self._prompts:
            if p["id"] == prompt_id:
                p["name"] = name
                p["content"] = content
                self._save()
                return True
        return False

    def delete(self, prompt_id: str) -> bool:
        """Delete prompt."""
        if prompt_id == "default":
            return False  # Disallow deleting the default prompt
        for i, p in enumerate(self._prompts):
            if p["id"] == prompt_id:
                self._prompts.pop(i)
                self._save()
                return True
        return False

    def get_names(self) -> list[str]:
        """Get all prompt names."""
        return [p["name"] for p in self._prompts]

    def get_ids(self) -> list[str]:
        """Get all prompt IDs."""
        return [p["id"] for p in self._prompts]
