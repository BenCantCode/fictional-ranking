from functools import cache
from mediawiki import (
    MediaWiki,
    WikiArticle,
    wikitext_transformer,
    replace_templates,
    Template,
)
from wikitextparser import WikiText, parse, Section
from exceptions import NotACharacterException, ParseException
import logging
from typing import Iterable
from character import Character
import re

logger = logging.getLogger(__name__)

CHARACTER_PATTERN = re.compile("{{\\s*Marvel Database:\\s*Character Template")


class MarvelWiki(MediaWiki):
    SOURCE_ID = "marvel"

    # TODO: Fix Egros. He works in the latest versions of the page, but the dump hasn't been updated.
    # See https://marvel.fandom.com/wiki/Egros_(Earth-616)?diff=9025795&oldid=8868774
    DUMP_URL = "https://s3.amazonaws.com/wikia_xml_dumps/e/en/enmarveldatabase_pages_current.xml.7z"
    DUMP_FORMAT = "7z"

    WIKI_URL = "https://marvel.fandom.com/wiki"

    SECTION_PRIORITY = {
        "introduction": 10,
        "attributes": 10,
        "powers": 9.9,
        "abilities": 9.8,
        "weaknesses": 9,
        "paraphernalia": 8,
        "history": 6,
        "origin": 7,
        "personality": 5,
        "notes": 2,
        "trivia": 2,
        "see also": 0,
        "links and references": 0,
    }

    # TODO: Remove this when the wiki updates.
    @wikitext_transformer(removes_information=False)
    def fix_egros(self, title: str, wikitext: WikiText):
        if title == "Egros (Earth-616)":
            wikitext.string = wikitext.string.replace(
                "{{m[|[Wanderers (Earth-616)|Wanderers]]}}", "{{m|Wanderers}}"
            )

    def _get_character_template(self, wikitext: WikiText) -> Template | None:
        return next(
            (
                template
                for template in wikitext.templates
                if template.normal_name().strip().endswith("Character Template")
            ),
            None,
        )

    def extract_aliases(self, title: str, parsed: WikiText):
        character_template = self._get_character_template(parsed)
        if character_template is None:
            raise NotACharacterException(title)
        current_alias = character_template.get_arg("CurrentAlias")
        if not current_alias:
            return []
        return [parse(current_alias.value).plain_text().strip()]

    @wikitext_transformer
    def expand_membership(self, title: str, wikitext: WikiText):
        """
        The membership template automatically includes a character in a universe-specific group.
        See https://marvel.fandom.com/wiki/Module:Members.
        """

        template = next(
            (
                template
                for template in wikitext.templates
                if template.normal_name().replace("Marvel Database:", "").strip()
                in [
                    "Character Template",
                    "Team Template",
                    "Organization Template",
                    "Race Template",
                    "Item Template",
                    "Vehicle Template",
                    "Location Template",
                ]
            ),
            None,
        )
        if not template:
            raise ParseException("No template included; cannot determine reality.")
        # TODO: Handle "Moira" edge cases (see https://marvel.fandom.com/wiki/Module:Reality)
        reality = template.get_arg("Reality")
        if reality:
            reality = reality.plain_text()

        def member_to_text(template: Template):
            if template.normal_name() == "m":
                return template.arguments[0].plain_text()

        replace_templates(wikitext, member_to_text)

    @wikitext_transformer
    def expand_character_template(self, title: str, wikitext: WikiText):
        character_template = self._get_character_template(wikitext)
        if not character_template:
            logger.info(
                "%s does not use a character template; are they really a character?",
                title,
            )
            return

        arguments = dict(
            (arg.name.strip(), arg.value.strip())
            for arg in character_template.arguments
        )

        new_sections = []

        def add_section(argument_name, header):
            value = arguments.get(argument_name)
            if value:
                new_sections.append(f"{header}\n\n{value}")

        add_section("Overview", "")
        # TODO: Consider adding additional sections (see https://marvel.fandom.com/wiki/Marvel_Database:Character_Template) for full list
        add_section("History", "==History==")
        add_section("Personality", "==Personality==")
        if (
            "Powers" in arguments
            or "Abilities" in arguments
            or "Weaknesses" in arguments
        ):
            new_sections.append("==Attributes==")
        add_section("Powers", "===Powers===")
        add_section("Abilities", "===Abilities===")
        add_section(
            "AdditionalAttributes",
            "===Additional Attributes===",  # TODO: Check if this header is correct.
        )
        if (
            arguments.get("Equipment")
            or arguments.get("Transportation")
            or arguments.get("Weapons")
        ):
            new_sections.append("==Paraphernalia==")
        add_section("Equipment", "===Equipment===")
        add_section("Transportation", "===Transportation===")
        add_section("Weapons", "===Weapons===")
        add_section("Notes", "==Notes==")

        wikitext.string = "\n".join(new_sections)

    @wikitext_transformer
    def expand_links(self, title: str, wikitext: WikiText):
        def link_replacer(template: Template):
            if template.normal_name() in [
                "cid",
                "cis",
                "cl",
                "el",
                "elt",
                "eltd",
                "ml",
                "Power Link",
                "sl",
                "sld",
                "vl",
            ]:
                return template.arguments[-1].value

        replace_templates(wikitext, link_replacer)

    def is_valid_character(self, name: str, article: WikiArticle):
        return super().is_valid_character(name, article) and any(
            re.finditer(CHARACTER_PATTERN, article.content)
        )

    def extract_image_name(self, title: str, wikitext: WikiText):
        character_box = self._get_character_template(wikitext)
        if not character_box:
            logger.info(
                "%s does not use a character template; are they really a character?",
                title,
            )
            return
        image = character_box.get_arg("Image")
        if image is None:
            return None
        return image.value.strip()
