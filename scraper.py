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
    #    "https://novelbin.com/n/shadow-slave-novel",
    "https://novelbin.com/b/supreme-magus",
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

# --- LLM CONFIGURATION ---
if USE_LLM_CLEANUP:
    if not GOOGLE_API_KEY:
        # We will let the script run for testing, but raise error later if used.
        llm_model = None
    else:
        genai.configure(api_key=GOOGLE_API_KEY)
        llm_model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
else:
    llm_model = None

# --- HELPER FUNCTIONS (CORRECT IMPLEMENTATIONS) ---


def sanitize_filename(name):
    """Removes invalid characters for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def basic_clean_text(text):
    """Performs basic, non-LLM cleaning."""
    # This corrected regex now looks for optional punctuation [.,!] and whitespace \s*
    # after the promotional text and removes it all.
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

    # A final strip() removes any leading/trailing whitespace from the whole string.
    return text.strip()


def llm_edit_text(text_chunk):
    """Sends a chunk of text to the LLM for editing."""
    if not text_chunk.strip():
        return ""

    # This check is important so tests can run without an API key
    if not llm_model:
        raise ConnectionError(
            "LLM model not configured. Did you set the GOOGLE_API_KEY?"
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
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 <= max_chars:  # +2 for \n\n
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def update_manifest():
    """Creates or updates a manifest.json file listing all .txt novels."""
    print("Updating manifest file...")
    novels = [f for f in os.listdir(REPO_PATH) if f.endswith(".txt")]
    manifest_path = os.path.join(REPO_PATH, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(novels, f, indent=2)
    print("Manifest updated successfully.")


# --- CORE SCRAPING LOGIC with httpx ---


def scrape_novel(novel_url):
    """Scrapes an entire novel from its main page URL using httpx."""
    # Using a client block is best practice for managing connections
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        try:
            main_page = client.get(novel_url)
            main_page.raise_for_status()  # Checks for 4xx/5xx responses
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
                chapter_page = client.get(current_chapter_url)
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
                    print(
                        f"Could not find content for {current_chapter_url}. Stopping."
                    )
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

            print(
                f"--- Finished: Scraped {chapter_count} chapters for {novel_title} ---"
            )

        except httpx.RequestError as e:
            print(f"An HTTP error occurred: {e.__class__.__name__} - {e}")
        except Exception as e:
            print(f"A general error occurred: {e}")


# --- GIT & MAIN ---
def git_commit_and_push():
    """Commits and pushes changes to git repository."""
    try:
        repo = git.Repo(REPO_PATH)

        # Check if there are any changes
        if not repo.is_dirty() and not repo.untracked_files:
            print("No changes to commit.")
            return

        # Add all changes
        repo.git.add(A=True)

        # Commit with a timestamp
        commit_message = f"Update novels - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        repo.index.commit(commit_message)
        print(f"Committed changes: {commit_message}")

        # Push to origin
        origin = repo.remote(name="origin")
        origin.push()
        print("Pushed changes to remote repository.")

    except git.exc.InvalidGitRepositoryError:
        print("Not a git repository. Skipping git operations.")
    except Exception as e:
        print(f"Git operation failed: {e}")


if __name__ == "__main__":
    for url in NOVEL_URLS:
        scrape_novel(url)
    update_manifest()
    git_commit_and_push()
