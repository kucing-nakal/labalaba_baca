## Full scraper.py with chapter splitting, curl-cffi, and all advanced features.

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import time
import re
import os
import json
import git
import google.generativeai as genai
from urllib.parse import urljoin

# --- CONFIGURATION ---
REPO_PATH = "."
# The main "table of contents" page for each novel
NOVEL_URLS = [
    "https://novelbin.com/n/supreme-magus-novel/",
    # Add other novel URLs here, e.g., "https://novelbin.com/n/shadow-slave-novel/"
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

# --- HELPER FUNCTIONS ---


def sanitize_filename(name):
    """Removes invalid characters for filenames."""
    # Remove characters that are invalid in Windows/Mac/Linux filenames
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Also remove periods from the start of a filename
    name = re.sub(r"^\.", "", name)
    # Reduce multiple spaces to one
    name = re.sub(r"\s+", " ", name).strip()
    return name


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
    # The non-greedy regex to remove the ad block specifically
    text = re.sub(
        r"Enhance your reading experience.*?Remove Ads From \$1",
        "",
        text,
        flags=re.DOTALL,
    )
    return text.strip()


def llm_edit_text(text_chunk):
    """Sends a chunk of text to the LLM for editing."""
    if not text_chunk.strip():
        return ""
    if not llm_model:
        raise ConnectionError("LLM model not configured.")

    print("    > Sending chunk to LLM for editing...")
    try:
        full_prompt = EDITING_PROMPT.format(text_chunk)
        response = llm_model.generate_content(
            full_prompt, request_options={"timeout": 120}
        )
        time.sleep(1.5)  # Respect free tier rate limits
        if response.parts:
            return response.text
        else:
            print("    > WARNING: LLM returned no content. Returning original chunk.")
            return text_chunk
    except Exception as e:
        print(f"    > ERROR: LLM editing failed: {e}. Returning original chunk.")
        return text_chunk


def chunk_text(text, max_chars=4000):
    """Splits text into chunks for LLM processing."""
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


# --- CORE SCRAPING LOGIC ---


def scrape_novel(novel_url):
    """Scrapes an entire novel, saving each chapter as a separate file."""
    try:
        session = curl_requests.Session(impersonate="chrome120", timeout=30)
        print(f"Attempting to fetch main page with curl-cffi: {novel_url}")
        main_page = session.get(novel_url)
        main_page.raise_for_status()
        soup = BeautifulSoup(main_page.content, "html.parser")

        novel_title = soup.find("h3", class_="title").text.strip()
        novel_folder = sanitize_filename(novel_title)
        os.makedirs(novel_folder, exist_ok=True)
        print(f"--- Starting scrape for: {novel_title} ---")
        print(f"--- Saving chapters to folder: '{novel_folder}/' ---")

        first_chapter_span = soup.select_one(
            "span.nchr-text[data-novel_id][data-chapter_id]"
        )
        if not first_chapter_span:
            print("Could not find the first chapter's data-span. Exiting.")
            return

        novel_id = first_chapter_span.get("data-novel_id")
        chapter_id = first_chapter_span.get("data-chapter_id")
        if not novel_id or not chapter_id:
            print("Found the span, but it's missing data. Exiting.")
            return
        current_chapter_url = f"https://novelbin.com/b/{novel_id}/{chapter_id}"
        print(f"  (Manually constructed first chapter URL: {current_chapter_url})")

        chapter_count = 0
        chapter_manifest = []

        while current_chapter_url:
            if not current_chapter_url.startswith(("http://", "https://")):
                current_chapter_url = urljoin(novel_url, current_chapter_url)

            print(f"Scraping chapter: {current_chapter_url}")
            chapter_page = session.get(current_chapter_url)
            chapter_page.raise_for_status()
            chapter_soup = BeautifulSoup(chapter_page.content, "html.parser")

            title_element = chapter_soup.find("a", class_="chr-title")
            chapter_title = (
                title_element.get("title", "Untitled Chapter").strip()
                if title_element
                else "Untitled Chapter"
            )

            safe_chapter_title = sanitize_filename(chapter_title)
            chapter_filename = (
                f"{str(chapter_count + 1).zfill(4)}-{safe_chapter_title}.txt"
            )
            chapter_filepath = os.path.join(novel_folder, chapter_filename)

            content_div = chapter_soup.find(id="chr-content")
            if content_div:
                raw_text = content_div.get_text(separator="\n")
                cleaned_text = basic_clean_text(raw_text)

                final_text = cleaned_text  # Default to cleaned text
                if USE_LLM_CLEANUP and cleaned_text.strip():
                    print("    > Processing with LLM cleanup...")
                    text_chunks = chunk_text(cleaned_text)
                    edited_chunks = [llm_edit_text(chunk) for chunk in text_chunks]
                    final_text = "\n\n".join(edited_chunks)

                with open(chapter_filepath, "w", encoding="utf-8") as f:
                    f.write(final_text)

                chapter_manifest.append(
                    {
                        "number": chapter_count + 1,
                        "title": chapter_title,
                        "file": chapter_filename,
                    }
                )
            else:
                print(f"Could not find content for {current_chapter_url}.")

            chapter_count += 1

            next_link_element = chapter_soup.find(id="next_chap")
            if next_link_element and "disabled" not in next_link_element.get(
                "class", []
            ):
                current_chapter_url = next_link_element.get("href")
            else:
                print("Last chapter reached.")
                current_chapter_url = None

            time.sleep(1)

        manifest_filepath = os.path.join(novel_folder, "manifest.json")
        with open(manifest_filepath, "w", encoding="utf-8") as f:
            json.dump(chapter_manifest, f, indent=2)

        print(f"--- Finished: Scraped {chapter_count} chapters for {novel_title} ---")

    except curl_requests.errors.RequestsError as e:
        print(f"A web request error occurred: {e}")
    except Exception as e:
        print(f"A general error occurred: {e}")


# --- MANIFEST AND GIT ---


def update_main_manifest():
    """Creates a main manifest listing all valid novel FOLDERS."""
    print("Updating main manifest file...")
    # Find directories that contain a 'manifest.json' file, ignoring hidden ones.
    novels = [
        d
        for d in os.listdir(REPO_PATH)
        if os.path.isdir(os.path.join(REPO_PATH, d))
        and not d.startswith((".", "venv"))
        and os.path.exists(os.path.join(REPO_PATH, d, "manifest.json"))
    ]
    manifest_path = os.path.join(REPO_PATH, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(novels, f, indent=2)
    print("Main manifest updated successfully.")


def git_commit_and_push():
    """Commits and pushes changes to the git repository."""
    try:
        repo = git.Repo(REPO_PATH)
        if not repo.is_dirty(untracked_files=True):
            print("No changes to commit. Repository is up-to-date.")
            return

        print("Adding all changes to git...")
        repo.git.add(A=True)

        commit_message = f"Update novels - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        repo.index.commit(commit_message)
        print(f"Committed changes: {commit_message}")

        origin = repo.remote(name="origin")
        print("Pushing changes to remote repository...")
        origin.push()
        print("Push successful.")

    except git.exc.InvalidGitRepositoryError:
        print("Not a git repository. Skipping git operations.")
    except Exception as e:
        print(f"Git operation failed: {e}")


# --- MAIN EXECUTION BLOCK ---

if __name__ == "__main__":
    if USE_LLM_CLEANUP and not llm_model:
        print(
            "WARNING: LLM cleanup is enabled but model is not configured. Skipping LLM pass."
        )
        USE_LLM_CLEANUP = False

    for url in NOVEL_URLS:
        scrape_novel(url)

    update_main_manifest()
    git_commit_and_push()
