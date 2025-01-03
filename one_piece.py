from __future__ import annotations
from typing import Iterable
from mediawiki import (
    MediaWiki,
    WikiArticle,
    combine_subpages,
    replace_templates,
    wikitext_transformer,
)
from character import Character
import wikitextparser as wtp
from wikitextparser import Template, WikiText

DEFAULT_TAB_SUBPAGES = set(
    [
        "Gallery",
        "Personality and Relationships",
        "Personality",
        "Relationships",
        "Abilities and Powers",
        "History",
    ]
)


class OnePieceWiki(MediaWiki):
    SOURCE_ID = "one_piece"

    WIKI_URL = "https://onepiece.fandom.com/wiki"

    DUMP_URL = (
        "https://s3.amazonaws.com/wikia_xml_dumps/o/on/onepiece_pages_current.xml.7z"
    )
    DUMP_FORMAT = "7z"

    # The "List of Canon Characters" isn't perfect.
    IGNORE_CHARACTER_NAMES = [
        "Impel Down",
        "Mock Town",
        "Rocks Pirates",
        "Belly",
        "Sapoten Graveyard",
        "Rock",
        "Fude Fude no Mi",
    ]

    SECTION_PRIORITY = {
        "introduction": 10,
        "abilities and powers": 10,
        "history": 8,
        "final": 7.9,
        "wano": 7.8,
        "whole cake": 7.7,
        "new world": 7.6,
        "summit war": 7.5,
        "paradise": 7.4,
        "east blue": 7.3,
        "personality": 5,
        "major battles": 6,  # Doesn't actually contain outcomes
        "relationships": 6,
        "trivia": 2,
        "translations and dub issues": 1,
        "translation and dub issues": 1,
        "links": 0,
        "other media": 0,
        "etymology": 0.2,
        "censorship": 0.2,
        "anime and manga differences": 0.5,
        "non-canon": 0.1,
        "other appearances": 0.1,
        "early concepts": 0,
        "gallery": 0,
        "merchandise": 0,
        "site navigation": 0,
        "external links": 0,
        "references": 0,
    }

    IMAGE_LOCATIONS = [
        "{title} Anime Post Timeskip Infobox.png",
        "{title} Manga Post Timeskip Infobox.png",
        "{title} Anime Infobox.png",
        "{title} Manga Infobox.png",
        "{title} Infobox.png",
    ]

    # Extract relevant pages from a tab template
    # Only used on the Wiki page for Monkey D. Luffy
    def pages_from_tabs(self, tabs: Template) -> tuple[str, list[WikiArticle]]:
        pages = []
        root = next(
            (arg.value.strip() for arg in tabs.arguments if arg.name.strip() == "root"),
            "",
        )
        pages.extend(
            self.get_article(root + "/" + arg.value.strip())
            for arg in tabs.arguments
            if arg.name.strip().startswith("tab ")
            and not arg.name.strip().endswith("title")
            and not arg.name.strip().endswith("tooltip")
        )
        for subtab in (
            wtp.parse(arg.value).templates[0]
            for arg in tabs.arguments
            if arg.name.strip().startswith("subtab")
            and not arg.name.strip().endswith("title")
            and not arg.name.strip().endswith("tooltip")
        ):
            subtab_root, subtab_pages = self.pages_from_tabs(subtab)
            try:
                subtab_index = (
                    next(
                        i
                        for i, page in enumerate(pages)
                        if isinstance(page, WikiArticle) and page.title == subtab_root
                    )
                    + 1
                )
                pages.insert(subtab_index, subtab_pages)
            except ValueError:
                pages.append(subtab_pages)
        return (root, pages)

    @wikitext_transformer
    def expand_character_tabs(self, title: str, wikitext: WikiText):
        tabs_template_used = next(
            (
                template
                for template in wikitext.templates
                if template.normal_name().endswith(" Tabs Top")
            ),
            None,
        )
        if not tabs_template_used:
            return
        character_name = tabs_template_used.normal_name()[: -len(" Tabs Top")]
        tab_template = self.get_article(
            f"Template:{tabs_template_used.normal_name()}"
        ).content  # type: ignore
        parsed_tab_template = wtp.parse(tab_template)
        if any(
            template
            for template in parsed_tab_template.templates
            if template.normal_name() == "Character Tab"
        ):
            subpages = [
                page
                for page in (
                    self.get_article(f"{character_name}/{suffix}")
                    for suffix in DEFAULT_TAB_SUBPAGES
                )
                if page != None
            ]
        else:
            subpages: list[WikiArticle] = self.pages_from_tabs(
                next(
                    template
                    for template in parsed_tab_template.templates
                    if template.normal_name() == "Tabs"
                ),
            )[1]
        wikitext.string = wikitext.string + combine_subpages(1, subpages)  # type: ignore

    @wikitext_transformer
    def expand_nihongo(self, title: str, wikitext: WikiText):
        def replace_nihongo(template: Template):
            if template.normal_name(capitalize=True) == "Nihongo":
                return template.arguments[0].value

        replace_templates(wikitext, replace_nihongo)

    def _all_character_names(self) -> Iterable[str]:
        character_names = set()
        for character_list in self.articles_starting_with(
            "List of Canon Characters/Names"
        ):
            # Hack to add table begin/end syntax because these articles are meant to be included in a larger list
            parsed = wtp.parse(
                "{|\n"
                + "\n".join(
                    line
                    for line in character_list.content.splitlines()
                    if line.startswith("|")
                )
                + "\n|}"
            )
            data = parsed.get_tables()[0].data()
            for row in data:
                link = wtp.parse(row[1]).wikilinks[0]
                character_names.add(link.title)
        for character in self.IGNORE_CHARACTER_NAMES:
            character_names.discard(character)
        return character_names

    def is_valid_character(self, name: str, article: WikiArticle):
        return (
            super().is_valid_character(name, article)
            and name in self.all_character_names()
        )

    def extract_image_name(self, title: str, parsed: WikiText) -> str | None:
        for location in self.IMAGE_LOCATIONS:
            location = location.format(title=title)
            if ("File:" + location) in self.articles:
                return location
        return None
