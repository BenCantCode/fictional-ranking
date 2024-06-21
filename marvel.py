from mediawiki import (
    MediaWiki,
    WikiArticle,
    wikitext_transformer,
    replace_templates,
    Template,
)
from wikitextparser import WikiText, parse, Section
from exceptions import ParseException
import logging
from typing import Iterable
from character import Character

logger = logging.getLogger(__name__)


class MarvelWiki(MediaWiki):
    SOURCE_ID = "marvel"

    # TODO: Fix Egros. He works in the latest versions of the page, but the dump hasn't been updated.
    # See https://marvel.fandom.com/wiki/Egros_(Earth-616)?diff=9025795&oldid=8868774
    DUMP_URL = "https://s3.amazonaws.com/wikia_xml_dumps/e/en/enmarveldatabase_pages_current.xml.7z"
    DUMP_FORMAT = "7z"

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

    INCLUDE_CATEGORIES = [
        "Category:Multiverse/Characters",
        "Category:Fantastic Four (Earth-616)/Members",
        "Category:Avengers (Earth-616)/Members",
        "Category:New Avengers (Earth-616)/Members",
        "Category:X-Men (Earth-616)",
        "Category:Guardians of the Galaxy (Earth-616)/Members",
        "Category:House of Agon (Earth-616)/Members",
        "Category:Runaways (Earth-616)/Members",
    ]

    INCLUDE_CHARACTERS = [
        "Category:Fantastic Four (Earth-616)/Members",
        "Category:Avengers (Earth-616)/Members",
        "Category:New Avengers (Earth-616)/Members",
        "Category:X-Men (Earth-616)",
        "Category:Guardians of the Galaxy (Earth-616)/Members",
        "Category:House of Agon (Earth-616)/Members",
        "Category:Runaways (Earth-616)/Members",
    ]

    def article_filter(self, article: WikiArticle):
        return article.title.endswith(" (Earth-616)") and len(article.content) > 10000

    @wikitext_transformer
    def expand_membership(self, title: str, wikitext: WikiText):
        """
        The membership template automatically includes a character in a universe-specific group.
        See https://marvel.fandom.com/wiki/Module:Members.
        """
        # TODO: Remove this when the wiki updates.
        if title == "Egros (Earth-616)":
            wikitext.string.replace(
                "{{m[|[Wanderers (Earth-616)|Wanderers]]}}", "{{m|Wanderers}}"
            )
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
        template = next(
            (
                template
                for template in wikitext.templates
                if template.normal_name().replace("Marvel Database:", "").strip()
                in ["Character Template"]
            ),
            None,
        )
        if not template:
            logger.info(
                "%s does not use a character template; are they really a character?"
            )
            return

        arguments = dict(
            (arg.name.strip(), arg.value.strip()) for arg in template.arguments
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
        if "Equipment" or "Transportation" in arguments or "Weapons" in arguments:
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
