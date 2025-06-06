import httpx
from bs4 import BeautifulSoup
import time
import re
import os
import json
import git
import google.generativeai as genai

# --- CONFIGURATION (No changes needed) ---
REPO_PATH = "."
NOVEL_URLS = [
    "https://novelbin.com/n/shadow-slave-novel",
    "https://novelbin.com/n/supreme-magus",
]
USE_LLM_CLEANUP = True
GOOGLE_API_KEY = os.getenv("KUCING_NAKAL_GOOGLE_API_KEY")
# The prompt for the LLM. Be very specific about what you want.
EDITING_PROMPT = """
You are an expert editor for web novels. Please proofread and lightly edit the following text.
Your tasks are:
1. Correct spelling mistakes, grammatical errors, and typos.
2. Fix awkward phrasing to improve readability, but preserve the original author's style.
3. Ensure consistent formatting for dialogue (e.g., using "quotation marks").
4. DO NOT add, remove, or change any story content, plot points, or character names.
5. DO NOT add any introductory or concluding remarks of your own.
Return only the edited text.

Here is the text:
---
{}
"""

# --- LLM CONFIGURATION (No changes needed) ---
if USE_LLM_CLEANUP:
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=GOOGLE_API_KEY)
    llm_model = genai.GenerativeModel("gemini-pro")


# --- HELPER FUNCTIONS (No changes needed) ---
def sanitize_filename(name):
    # ... same as before
    return re.sub(r'[\\/*?:"<>|]', "", name)


def basic_clean_text(text):
    # ... same as before
    return text  # Placeholder


def llm_edit_text(text_chunk):
    # ... same as before
    return text_chunk  # Placeholder


def update_manifest():
    # ... same as before
    pass  # Placeholder


# --- CORE SCRAPING LOGIC with httpx ---


def scrape_novel(novel_url):
    """Scrapes an entire novel from its main page URL using httpx."""
    # Using a client block is best practice for managing connections
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        try:
            main_page = client.get(novel_url)
            main_page.raise_for_status()  # Checks for 4xx/5xx responses
            soup = BeautifulSoup(main_page.content, "html.parser")

            novel_title = soup.find("h3", class_="title").text.strip()
            filename = f"{sanitize_filename(novel_title)}.txt"
            print(f"--- Starting scrape for: {novel_title} ---")

            first_chapter_link = soup.select_one("#list-chapter .chapter-name a")
            if not first_chapter_link:
                print(f"Could not find first chapter link for {novel_title}. Skipping.")
                return

            current_chapter_url = first_chapter_link["href"]

            if os.path.exists(filename):
                os.remove(filename)

            chapter_count = 0
            while current_chapter_url:
                print(f"Scraping chapter: {current_chapter_url}")
                chapter_page = client.get(current_chapter_url)  # <-- Change
                chapter_page.raise_for_status()

                chapter_soup = BeautifulSoup(chapter_page.content, "html.parser")
                chapter_title = (
                    chapter_soup.find("a", class_="chr-title")
                    .get("title", "Untitled Chapter")
                    .strip()
                )
                content_div = chapter_soup.find(id="chr-content")

                if not content_div:
                    print(
                        f"Could not find content for {current_chapter_url}. Stopping."
                    )
                    break

                raw_text = content_div.get_text(separator="\n")
                cleaned_text = basic_clean_text(raw_text)

                if USE_LLM_CLEANUP:
                    # ... LLM logic remains the same
                    final_text = cleaned_text  # Placeholder
                else:
                    final_text = cleaned_text

                with open(filename, "a", encoding="utf-8") as f:
                    f.write(f"## {chapter_title}\n\n")
                    f.write(final_text)
                    f.write("\n\n---\n\n")

                chapter_count += 1

                next_chapter_link = chapter_soup.find(id="next_chap")
                if next_chapter_link and "disabled" not in next_chapter_link.get(
                    "class", []
                ):
                    current_chapter_url = next_chapter_link["href"]
                    time.sleep(1)
                else:
                    print("Last chapter reached.")
                    current_chapter_url = None

            print(
                f"--- Finished: Scraped {chapter_count} chapters for {novel_title} ---"
            )

        except httpx.RequestError as e:  # <-- Change
            print(f"An HTTP error occurred: {e.__class__.__name__} - {e.request.url}")
        except Exception as e:
            print(f"A general error occurred: {e}")


# --- GIT & MAIN (No changes needed) ---
def git_commit_and_push():
    # ... same as before
    pass


if __name__ == "__main__":
    for url in NOVEL_URLS:
        scrape_novel(url)
    update_manifest()
    # git_commit_and_push()
