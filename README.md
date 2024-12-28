# Fictional Character Ranking System

Tier list for every fictional character, generated intelligently using LLMs.

## State of Project

This project is largely the result of work performed in the first half of 2024, and therefore does not reflect more recent changes in the AI landscape (e.g. batching and new models). A hosted version of the results can be found on my [blog](https://bengarvin.dev) featuring characters from Marvel and One Piece. If you're interested in the results dataset, feel free to open an issue here explaining your use case.

## Fandom

The primary data source for this project is wiki pages, and the largest wiki hosting platform is Fandom. Fandom provides occasional dumps of the text content of its wikis on the `Special:Statistics` pages, which contain all the information necessary for running evaluations.

Fandom does not, however, provide similar dumps of its image content. Character images are an important part of the standard tier list format, so this poses a significant problem. It's important to note that Fandom doesn't have any special rights to character images; they're just using them under the assumption of fair use like everybody else. For that reason, it makes sense that they aren't providing download links.

To get around this restriction, as well as several clauses in Fandom's TOS that bar using "any robot, spider, site search and/or retrieval application, or other device to scrape, extract, retrieve or index any portion of the content," images from Fandom are embedded in the tier list page via `<img>` tags that link to Fandom's website. This is not only a legal measure, it also allows images used on the tier list to be more up-to-date and allows Fandom to block our access to these images at any time (via CORS headers) should they so choose. In order to lessen the load on Fandom's infrastructure, character images are lazily-loaded when possible.

I'd like to mention that most automated robots (e.g. [Google's](https://www.google.com/search?q=site:fandom.com&udm=2)) don't bother reading every website's terms of service and will happily download and store a website's text and image content so long as doing so isn't prohibited by the website's `robots.txt` (Fandom's is fairly lenient). The fact that this project doesn't do so is an attempt to go above and beyond to respect Fandom's wishes and wouldn't be considered a requirement under standard web scraping conventions.

If any Fandom representatives happen to be reading this, I'd love to self-host character images for use on the tier list, which would remove any (hopefully negligible) load the tier list places on your servers. Doing so would also allow this project to use facial recognition tools to crop character images, resulting in a better looking tier list. If you have the power to make this happen (e.g. by providing dumps or allowing automatic image downloads), feel free to open a GitHub issue here. 🙂

## Running/Developing

This project uses the `uv` package management tool for Python.

1. Add API keys to a `.env` file or environment variables (see LiteLLM docs for details).
2. Initialize a database using `uv run db.py init`. Then, set up a run by configuring settings in `config.py` and editing the `stats.py` script. Once you're satisfied with the settings for the run, start it using `uv run stats.py`. Note that runs can also be continued if prematurely interrupted (see the comments in `stats.py`).
3. Generate `results.html` using `uv run tier_list.py`.
