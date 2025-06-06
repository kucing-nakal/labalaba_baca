# Full scraper.py using curl-cffi to bypass advanced bot detection

# --- UPDATED IMPORTS ---
from curl_cffi import requests as curl_requests  # Use the requests-compatible API
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
    "https://novelbin.com/b/supreme-magus",
]
USE_LLM_CLEANUP = True
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

# --- LLM CONFIGURATION ---
if USE_LLM_CLEANUP:
    API_KEY = os.getenv("KUCING_NAKAL_GOOGLE_API_KEY")
    if not API_KEY:
        llm_model = None
    else:
        genai.configure(api_key=API_KEY)
        llm_model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
else:
    llm_model = None

# --- HELPER FUNCTIONS (No changes needed) ---


def sanitize_filename(name):
    """Removes invalid characters for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def basic_clean_text(text):
    """Performs basic, non-LLM cleaning."""
    text = re.sub(
        r"Read latest Chapters at novelbin\.com Only[.,!\s]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"This chapter is updated by novelbin\.com[.,!\s]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def llm_edit_text(text_chunk):
    """Sends a chunk of text to the LLM for editing."""
    if not text_chunk.strip():
        return ""
    if not llm_model:
        raise ConnectionError(
            "LLM model not configured. Did you set the KUCING_NAKAL_GOOGLE_API_KEY?"
        )
    print("    > Sending chunk to LLM for editing...")
    try:
        full_prompt = EDITING_PROMPT.format(text_chunk)
        response = llm_model.generate_content(full_prompt)
        time.sleep(1.5)
        if response.parts:
            return response.text
        else:
            print("    > WARNING: LLM returned no content. Returning original chunk.")
            return text_chunk
    except Exception as e:
        print(f"    > ERROR: LLM editing failed: {e}. Returning original chunk.")
        return text_chunk


def chunk_text(text, max_chars=4000):
    """Split text into chunks for LLM processing to avoid token limits."""
    # This function is well-written and doesn't need changes.
    if len(text) <= max_chars:
        return [text]
    chunks, paragraphs, current_chunk = [], text.split("\n\n"), ""
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 <= max_chars:
            current_chunk += ("\n\n" if current_chunk else "") + paragraph
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def update_manifest():
    """Creates or updates a manifest.json file listing all .txt novels."""
    # This function is fine and doesn't need changes.
    print("Updating manifest file...")
    novels = [f for f in os.listdir(REPO_PATH) if f.endswith(".txt")]
    manifest_path = os.path.join(REPO_PATH, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(novels, f, indent=2)
    print("Manifest updated successfully.")


# --- CORE SCRAPING LOGIC with curl-cffi ---


def scrape_novel(novel_url):
    """Scrapes an entire novel, impersonating a browser with curl_cffi."""
    try:
        # The 'impersonate' argument is the key. It automatically sets all the
        # necessary headers and TLS settings to mimic a real browser.
        # We use a Session object for connection pooling and cookie handling.
        session = curl_requests.Session(impersonate="chrome120", timeout=30)

        print(f"Attempting to fetch main page with curl-cffi: {novel_url}")
        main_page = session.get(novel_url)
        main_page.raise_for_status()
        soup = BeautifulSoup(main_page.content, "html.parser")

        title_element = soup.find("h3", class_="title")
        if not title_element:
            print(f"Could not find title for {novel_url}. Skipping.")
            return

        novel_title = title_element.text.strip()
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
            # Use the same session for all subsequent requests
            chapter_page = session.get(current_chapter_url)
            chapter_page.raise_for_status()

            chapter_soup = BeautifulSoup(chapter_page.content, "html.parser")
            title_element = chapter_soup.find("a", class_="chr-title")
            chapter_title = (
                title_element.get("title", "Untitled Chapter").strip()
                if title_element
                else "Untitled Chapter"
            )
            content_div = chapter_soup.find(id="chr-content")

            if not content_div:
                print(f"Could not find content for {current_chapter_url}. Stopping.")
                break

            raw_text = content_div.get_text(separator="\n")
            cleaned_text = basic_clean_text(raw_text)

            if USE_LLM_CLEANUP and cleaned_text.strip():
                print("    > Processing with LLM cleanup...")
                text_chunks = chunk_text(cleaned_text)
                edited_chunks = []
                for i, chunk in enumerate(text_chunks):
                    print(f"    > Processing chunk {i + 1}/{len(text_chunks)}")
                    edited_chunk = llm_edit_text(chunk)
                    edited_chunks.append(edited_chunk)
                final_text = "\n\n".join(edited_chunks)
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

        print(f"--- Finished: Scraped {chapter_count} chapters for {novel_title} ---")

    # UPDATED EXCEPTION HANDLING for curl_cffi
    except curl_requests.errors.RequestsError as e:
        print(f"A web request error occurred: {e}")
    except Exception as e:
        print(f"A general error occurred: {e}")


# --- GIT & MAIN (No changes needed) ---
def git_commit_and_push():
    """Commits and pushes changes to git repository."""
    try:
        repo = git.Repo(REPO_PATH)
        if not repo.is_dirty(untracked_files=True):
            print("No changes to commit.")
            return
        repo.git.add(A=True)
        commit_message = f"Update novels - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        repo.index.commit(commit_message)
        print(f"Committed changes: {commit_message}")
        origin = repo.remote(name="origin")
        origin.push()
        print("Pushed changes to remote repository.")
    except git.exc.InvalidGitRepositoryError:
        print("Not a git repository. Skipping git operations.")
    except Exception as e:
        print(f"Git operation failed: {e}")


if __name__ == "__main__":
    if USE_LLM_CLEANUP and not llm_model:
        print(
            "WARNING: LLM cleanup is enabled but model is not configured. Skipping LLM pass."
        )
        USE_LLM_CLEANUP = False

    for url in NOVEL_URLS:
        scrape_novel(url)

    update_manifest()
    git_commit_and_push()
