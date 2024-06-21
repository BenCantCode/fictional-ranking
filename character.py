from litellm import token_counter, completion_cost
from litellm.exceptions import NotFoundError


class Section:
    def __init__(self, text: str, priority: int):
        self.text = text
        self.priority = priority

    def combine_sections(sections):
        return "\n".join([section.text for section in sections])

    def __str__(self):
        return f'(Section "{self.text.strip().splitlines()[0][0:100]}")'

    def __repr__(self):
        return f'(Section "{self.text.strip().splitlines()[0][0:100]}")'


class Character:
    def __init__(self, name: str, sections: list[Section], source: str):
        self.name = name
        self.sections = sections
        self.source = source

    @property
    def full_text(self):
        return Section.combine_sections(self.sections)

    def abridged_text(
        self,
        model: str = None,
        max_characters: int = None,
        max_tokens: int = None,
        max_cost: int = None,
    ) -> str:
        abridged_sections = [
            section for section in self.sections if section.priority > 0
        ]
        text = Section.combine_sections(abridged_sections)
        while (
            (max_characters != None and len(text) > max_characters)
            or (max_tokens != None and token_counter(model, text=text) > max_tokens)
            or (max_cost != None and completion_cost(model, prompt=text) > max_cost)
        ):
            abridged_sections.remove(
                min(abridged_sections, key=lambda section: section.priority)
            )
            text = Section.combine_sections(abridged_sections)
        return text

    @property
    def id(self):
        return f"{self.source}/{self.name}"
