from __future__ import annotations
from datetime import datetime
from typing import Iterable, Callable, TypeAlias, Union, IO
from lxml.etree import iterparse, ElementBase
from source import Source
from urllib.request import urlretrieve
from urllib.parse import quote_plus
import os
from os.path import join, exists
import pickle
from character import CharacterId, Section, Character
import wikitextparser as wtp
from wikitextparser import Template, WikiText, WikiLink
from wikitextparser._spans import parse_to_spans
import re
import zstandard
import requests
from py7zr import SevenZipFile
from config import *
from functools import wraps
from exceptions import NotACharacterException
from dateutil.parser import parse as parsedate

NAMESPACE = "http://www.mediawiki.org/xml/export-0.11/"


class WikiArticle:
    title: str
    revision: datetime
    content: str
    namespace: int

    def __init__(self, el: ElementBase, namespace=NAMESPACE):
        ns = {"mw": namespace}
        self.title = el.findtext(f"mw:title", namespaces=ns)  # type: ignore
        text = el.findtext(f"mw:revision/mw:text", namespaces=ns)
        self.revision = parsedate(el.findtext(f"mw:revision/mw:timestamp", namespaces=ns))  # type: ignore
        self.namespace = int(el.findtext(f"mw:ns", namespaces=ns))  # type: ignore
        if text:
            self.content = text
        else:
            self.content = ""

    def __str__(self):
        return f'(Article "{self.title}")'

    def __repr__(self):
        return f'(Article "{self.title}")'


DeepPagesList: TypeAlias = list[Union[WikiArticle, "DeepPagesList"]]


def combine_subpages(depth, pages: DeepPagesList) -> str:
    content = ""
    for el in pages:
        if isinstance(el, WikiArticle):
            if el.title:
                content = content + f"\n=={el.title.split('/')[-1]}==\n"
            parsed = wtp.parse(el.content)
            for section in parsed.get_sections(include_subsections=False):
                if section.level:
                    section.level += depth
                content = content + "\n" + section.string
        elif isinstance(el, list):
            content = content + "\n" + combine_subpages(depth + 1, el)
        else:
            raise TypeError(f"Subpage element {el} is not a WikiPage or List")
    return content


# Used to determine transformer order.
_transformer_count = 0


def wikitext_transformer(method):
    global _transformer_count
    method._wikitext_transformer = _transformer_count
    _transformer_count += 1
    return method


def replace_templates(wikitext: WikiText, replacer: Callable[[Template], str | None]):
    index = 0
    while True:
        templates = wikitext.templates
        if index >= len(templates):
            break
        template = templates[index]
        replacement = replacer(template)
        if replacement == None:
            index += 1
            continue
        span = template.span
        old_string = wikitext.string
        wikitext.string = old_string[: span[0]] + replacement + old_string[span[1] :]


def replace_wikilinks(wikitext: WikiText, replacer: Callable[[WikiLink], str | None]):
    index = 0
    while True:
        wikilinks = wikitext.wikilinks
        if index >= len(wikilinks):
            break
        wikilink = wikilinks[index]
        replacement = replacer(wikilink)
        if replacement == None:
            index += 1
            continue
        span = wikilink.span
        old_string = wikitext.string
        wikitext.string = old_string[: span[0]] + replacement + old_string[span[1] :]


class MediaWiki(Source):
    # The URL of the dump
    DUMP_URL: str
    # The format of the dump (if it's an archive, it will be extracted)
    DUMP_FORMAT: str = "xml"

    API_URL: str | None = None

    # 10-0: Chance (out of 10) that the information is relevant.
    # 0 means always omit.
    SECTION_PRIORITY: dict[str, float] = {}
    DEFAULT_SECTION_PRIORITY = 2

    def __init__(self, download_path: str = DOWNLOADS_FOLDER):
        self.cache_path = join(download_path, self.SOURCE_ID, "wiki.pickle.zst")
        self.dump_path = join(download_path, self.SOURCE_ID, "wiki.xml.7z")
        self.image_path = join(download_path, self.SOURCE_ID, "images")
        # Register template renderers
        self.wikitext_transformers = []
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_wikitext_transformer"):
                self.wikitext_transformers.append(method)
        self.wikitext_transformers.sort(key=lambda method: method._wikitext_transformer)
        super().__init__(download_path)

    @property
    def downloaded(self):
        return exists(self.cache_path)

    def parse_from_stream(self, stream: IO):
        self.articles = {}
        for action, elem in iterparse(stream):
            if action == "end":
                if elem.tag == f"{{{NAMESPACE}}}page":
                    if elem.findtext(f"{{{NAMESPACE}}}ns") in ["0", "6", "10", "14"]:
                        article = WikiArticle(elem)
                        self.articles[article.title] = article
        self.parsed = True

    def cache(self):
        print("Caching...")
        with open(self.cache_path, "wb") as cache:
            cctx = zstandard.ZstdCompressor()
            with cctx.stream_writer(cache) as writer:
                pickle.dump(self.articles, writer)
        print("Cached!")

    def parse(self):
        if self.parsed:
            # Already parsed.
            return
        if exists(self.cache_path):
            with open(self.cache_path, "rb") as cache:
                dctx = zstandard.ZstdDecompressor()
                with dctx.stream_reader(cache) as reader:
                    self.articles: dict[str, WikiArticle] = pickle.load(reader)
        elif exists(self.dump_path):
            if self.DUMP_FORMAT == "xml":
                with open(self.dump_path, "rb") as dump:
                    return self.parse_from_stream(dump)
            elif self.DUMP_FORMAT == "7z":
                with SevenZipFile(self.dump_path) as compressed_dump:
                    with next(iter(compressed_dump.readall().values())) as extracted:  # type: ignore
                        return self.parse_from_stream(extracted)
            else:
                raise NotImplementedError(self.DUMP_FORMAT)
            self.cache()
        else:
            raise Exception("Not downloaded!")

    async def download(self):
        os.makedirs(self.path, exist_ok=True)
        print("Downloading", self.DUMP_URL)
        tmp_download_path = None
        self.version = str(datetime.now())
        if not exists(self.dump_path):
            with open(self.dump_path, "wb") as local_dump:
                async with ASYNC_CLIENT.stream("GET", self.DUMP_URL) as remote_dump:
                    async for chunk in remote_dump.aiter_bytes():
                        local_dump.write(chunk)
                    if "last-modified" in remote_dump.headers:
                        self.version = str(
                            parsedate(remote_dump.headers["last-modified"])
                        )
            print("Downloaded!")
        else:
            print("Already downloaded!")
        print("Parsing...")
        self.parse()
        print("Parsed!")
        self.cache()
        if tmp_download_path:
            if not KEEP_ORIGINAL_DOWNLOADS:
                print("Deleting original...")
                os.remove(tmp_download_path)
                print("Deleted!")
        os.makedirs(self.image_path, exist_ok=True)

    def all_articles(self) -> Iterable[WikiArticle]:
        return iter(self.articles.values())

    def get_article(self, title) -> WikiArticle | None:
        return self.articles.get(title)

    def get_pages_in_category(
        self, category_name: str
    ) -> list[str]:  # e.g. Category:abcd
        """Gets the pages in each category from the MediaWiki API."""
        res = requests.get(
            f"{self.API_URL}?action=query&list=categorymembers&format=json&cmtype=page&cmtitle={quote_plus(category_name)}"
        )
        if res.ok:
            try:
                return [
                    member["title"] for member in res.json["query"]["categorymembers"]  # type: ignore
                ]
            except:
                raise ValueError("Malformed response.")
        else:
            raise ValueError("Category API request failed.")

    def articles_starting_with(self, title) -> Iterable[WikiArticle]:
        return (
            page
            for page_title, page in self.articles.items()
            if page_title.startswith(title)
        )

    def transform_wikitext(self, title: str, wikitext: WikiText):
        for transformer in self.wikitext_transformers:
            transformer(title, wikitext)
            # Hack to fix wikitext after transforming
            wikitext.__init__(wikitext.string)

    def extract_sections(self, article: WikiArticle):
        parsed = wtp.parse(article.content)
        self.transform_wikitext(article.title, parsed)
        # Extract sections
        sections = []
        found_level = None
        found_priority = self.DEFAULT_SECTION_PRIORITY
        i = 0
        for section in parsed.get_sections(include_subsections=False):
            i += 1
            found = False
            if section.title != None:
                title = section.title.strip()
                if title.lower() in self.SECTION_PRIORITY:  # type: ignore
                    found = True
                    found_level = section.level
                    found_priority = self.SECTION_PRIORITY[title.lower()]  # type: ignore
            if not found and found_level != None and section.level <= found_level:
                found_level = None
                found_priority = self.DEFAULT_SECTION_PRIORITY
            try:
                sections.append(
                    Section(
                        re.sub("[\n]+", "\n", section.plain_text()),
                        found_priority,
                    )
                )
            except Exception as e:
                print(article.title)
                raise e
        sections[0].text = "==Introduction==\n" + sections[0].text
        sections[0].priority = self.SECTION_PRIORITY["introduction"]
        return sections

    def _get_aliases(self, article: WikiArticle):
        return []

    def character_from_article(self, article: WikiArticle) -> Character:
        aliases = self._get_aliases(article)
        return Character(
            CharacterId(self.SOURCE_ID, article.title),
            str(article.revision),
            self.extract_sections(article),
            self,
            aliases,
        )

    def get_character(self, character_name: str) -> Character:
        article = self.get_article(character_name)
        if article == None or not self.article_filter(article):
            raise NotACharacterException(character_name)
        while article.content.startswith("#REDIRECT"):
            article = self.get_article(wtp.parse(article.content).wikilinks[0].title)
            if article == None:
                raise ValueError("Redirect goes to nonexistent page!")
        return self.character_from_article(article)

    def get_character_length_estimate(self, character_name: str) -> int:
        if character_name in self.articles:
            return len(self.articles[character_name].content)
        else:
            raise NotACharacterException(character_name)

    def article_filter(self, article: WikiArticle):
        return article.namespace == 0

    def all_characters(self) -> Iterable[Character]:
        for article in self.all_articles():
            if self.article_filter(article):
                try:
                    yield self.character_from_article(article)
                except NotACharacterException:
                    pass

    @wikitext_transformer
    def remove_images(self, title, wikitext: WikiText):
        def image_remover(wikilink: WikiLink):
            if wikilink.title.startswith("File:"):
                return ""

        replace_wikilinks(wikitext, image_remover)
