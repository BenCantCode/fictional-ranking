from __future__ import annotations
from litellm import token_counter, completion_cost
from typing import Iterable


class CharacterId:
    def __init__(self, source_id: str, name: str):
        self.source_id = source_id
        self.name = name

    def __str__(self):
        return f"{self.source_id}/{self.name}"


class Section:
    def __init__(self, text: str, priority: float):
        self.text = text
        self.priority = priority

    @staticmethod
    def combine_sections(sections: Iterable[Section]):
        return "\n".join([section.text for section in sections])

    def __str__(self):
        return f'(Section "{self.text.strip().splitlines()[0][0:100]}")'

    def __repr__(self):
        return f'(Section "{self.text.strip().splitlines()[0][0:100]}")'


class Character:
    def __init__(self, id: CharacterId, revision: str, sections: list[Section]):
        self.id = id
        self.sections = sections
        self.revision = revision

    @property
    def full_text(self):
        return Section.combine_sections(self.sections)

    def abridged_text(
        self,
        model: str | None = None,
        max_characters: int | None = None,
        max_tokens: int | None = None,
        max_cost: float | None = None,
    ) -> str:
        abridged_sections = [
            section for section in self.sections if section.priority > 0
        ]
        text = Section.combine_sections(abridged_sections)
        if (max_tokens != None or max_tokens != None) and not model:
            raise Exception(
                "No model provided, but one is required for max_tokens and max_cost."
            )
        while (
            (max_characters != None and len(text) > max_characters)
            or (max_tokens != None and token_counter(model, text=text) > max_tokens)  # type: ignore
            or (max_cost != None and completion_cost(model, prompt=text) > max_cost)  # type: ignore
        ):
            abridged_sections.remove(
                min(abridged_sections, key=lambda section: section.priority)
            )
            text = Section.combine_sections(abridged_sections)
        return text

    @property
    def name(self) -> str:
        return self.id.name

    @property
    def source_id(self) -> str:
        return self.id.source_id
