import requests
import xml.etree.ElementTree as ET
import json
import re
from bs4 import BeautifulSoup


def get_trending_keywords():
    countries = ["IN", "US", "GB", "CA", "AU"]
    all_keywords = []
    seen = set()

    for country in countries:
        url = (
            "https://trends.google.com/trending/rss"
            f"?geo={country}"
        )

        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):
                title = item.findtext("title")

                if title:
                    keyword = title.strip()
                    normalized = keyword.casefold()

                    if normalized not in seen:
                        seen.add(normalized)
                        all_keywords.append(keyword)

        except (requests.RequestException, ET.ParseError) as exc:
            print(f"Failed to fetch trends for {country}: {exc}")

    return all_keywords


def extract_json_text(value):
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        # Prefer common text-bearing fields when present.
        text_fields = [
            "text", "content", "children",
            "value", "html", "description"
        ]

        result = []

        for key in text_fields:
            if key in value:
                result.append(extract_json_text(value[key]))

        # Fall back to all values if no common fields exist.
        if not result:
            result = [
                extract_json_text(v)
                for v in value.values()
            ]

        return " ".join(result)

    if isinstance(value, list):
        return " ".join(extract_json_text(item) for item in value)

    return ""


def get_post_search_text(post):
    parts = [
        post.title or "",
        extract_json_text(post.content_json),
        BeautifulSoup(
            post.content_html or "",
            "html.parser"
        ).get_text(" ", strip=True),
        post.category.name if post.category else "",
    ]

    text = " ".join(part for part in parts if part).strip()

    print(f"Post {post.id}: extracted {len(text)} characters")

    return text
