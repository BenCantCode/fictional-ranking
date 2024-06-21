from mediawiki import MediaWiki, WikiArticle, wikitext_transformer
from wikitextparser import WikiText, parse


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

    def get_character_names(self):
        for article in self.all_articles():
            if article.title.endswith(" (Earth-616)") and len(article.content) > 10000:
                if any(
                    template
                    for template in parse(article.content).templates
                    if template.normal_name().replace("Marvel Database:", "").strip()
                    == "Character Template"
                ):
                    yield article.title

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
        infobox_template = next(
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
        if not infobox_template:
            print(
                [
                    template.normal_name().replace("Marvel Database:", "").strip()
                    for template in wikitext.templates
                ]
            )
            print("No template:", title)
            with open("error.txt", "w") as error:
                error.write(wikitext.string)
            return
        # TODO: Handle "Moira" edge cases (see https://marvel.fandom.com/wiki/Module:Reality)
        reality = infobox_template.get_arg("Reality")
        if reality:
            reality = reality.plain_text()
        for template in wikitext.templates:
            if template.normal_name() == "m":
                group = template.arguments[0].plain_text()
                template.string = f"[[Category:{group} ({reality}/Members)]]"

    @wikitext_transformer
    def expand_power(self, title: str, wikitext: WikiText):
        for template in wikitext.templates:
            if template.normal_name() == "Power Link":
                power = template.arguments[0].plain_text()
                template.string = f"[[{power}]]"
