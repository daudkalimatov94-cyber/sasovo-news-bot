import html
import json
import os
import re
from urllib.parse import quote

import feedparser
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

# Слова, по которым отбираем новости (в нижнем регистре, достаточно корня слова)
KEYWORDS = ["сасов"]

# Источники: (ссылка на RSS, нужен ли фильтр по ключевым словам)
FEEDS = [
    # Google News: поиск по слову «Сасово»
    (
        "https://news.google.com/rss/search?q="
        + quote("Сасово")
        + "&hl=ru&gl=RU&ceid=RU:ru",
        True,
    ),
    # Сюда можно добавлять свои сайты, например:
    # ("https://example.ru/feed/", True),    # региональный сайт, фильтр включён
    # ("https://local-site.ru/feed/", False),  # чисто сасовский сайт, фильтр не нужен
]

STATE_FILE = "posted.json"
MAX_POSTS_PER_RUN = 5


def load_posted():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_posted(posted):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(posted[-1000:], f, ensure_ascii=False, indent=2)


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def matches(entry):
    text = (clean(entry.get("title", "")) + " " + clean(entry.get("summary", ""))).lower()
    return any(k in text for k in KEYWORDS)


def send_message(title, summary, link):
    title = clean(title)
    summary = clean(summary)

    # Google News в описании часто повторяет заголовок, такое убираем
    if summary[:30] == title[:30]:
        summary = ""
    if len(summary) > 300:
        summary = summary[:300].rsplit(" ", 1)[0] + "…"

    text = f"<b>{html.escape(title)}</b>"
    if summary:
        text += f"\n\n{html.escape(summary)}"
    text += f'\n\n<a href="{html.escape(link)}">Читать полностью</a>'

    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=30,
    )
    r.raise_for_status()


def main():
    posted = load_posted()
    first_run = posted is None
    if first_run:
        posted = []

    new_items = []
    for url, use_filter in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            link = entry.get("link")
            if not link or link in posted:
                continue
            if use_filter and not matches(entry):
                continue
            new_items.append(entry)

    # Первый запуск: запоминаем текущие новости без отправки,
    # чтобы не завалить канал старыми постами
    if first_run:
        for entry in new_items:
            posted.append(entry["link"])
        save_posted(posted)
        return

    new_items.reverse()  # старые первыми
    for entry in new_items[:MAX_POSTS_PER_RUN]:
        send_message(
            entry.get("title", ""),
            entry.get("summary", ""),
            entry["link"],
        )
        posted.append(entry["link"])

    save_posted(posted)


if __name__ == "__main__":
    main()
