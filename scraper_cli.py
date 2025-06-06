# scraper_cli.py
# A flexible CLI for downloading and processing web novels with resume capability.

import os
import re
import json
import time
import argparse
import git
import random
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- CONFIGURATION ---
REPO_PATH = "."
EDITING_PROMPT = """..."""  # Your full prompt here
llm_model = None  # Will be initialized if needed


# --- HELPER FUNCTIONS ---
def initialize_llm():
    """Initializes the LLM model if it hasn't been already."""
    global llm_model
    if llm_model:
        return True
    API_KEY = os.getenv("KUCING_NAKAL_GOOGLE_API_KEY")
    if not API_KEY:
        print("WARNING: KUCING_NAKAL_GOOGLE_API_KEY not set. Cannot use LLM features.")
        return False
    try:
        import google.generativeai as genai

        genai.configure(api_key=API_KEY)
        llm_model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
        print("LLM Initialized successfully.")
        return True
    except Exception as e:
        print(f"Failed to initialize LLM: {e}")
        return False


def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"^\.", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def basic_clean_text(text):
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
    text = re.sub(
        r"Enhance your reading experience.*?Remove Ads From \$1",
        "",
        text,
        flags=re.DOTALL,
    )
    return text.strip()


def chunk_text(text, max_chars=4000):
    if len(text) <= max_chars:
        return [text]
    chunks, paragraphs, current_chunk = [], text.split("\n\n"), ""
    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 <= max_chars:
            current_chunk += ("\n\n" if current_chunk else "") + p
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = p
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


# --- CORE LOGIC ACTIONS ---


def action_download(novel_url):
    """Action: Downloads and cleans a novel, resuming if it already exists."""
    print("--- Action: Download ---")

    session = curl_requests.Session(impersonate="chrome120", timeout=30)

    try:
        print(f"Fetching main page to get novel title: {novel_url}")
        main_page = session.get(novel_url)
        main_page.raise_for_status()
        soup = BeautifulSoup(main_page.content, "html.parser")

        novel_title = soup.find("h3", class_="title").text.strip()
        novel_folder = sanitize_filename(novel_title)
        raw_folder = os.path.join(novel_folder, "raw_chapters")
        manifest_filepath = os.path.join(novel_folder, "manifest.json")

        os.makedirs(raw_folder, exist_ok=True)
        print(f"Novel: '{novel_title}'")

        chapter_manifest = []
        start_chapter_count = 0
        current_chapter_url = None

        if os.path.exists(manifest_filepath):
            print("Existing novel found. Attempting to resume download.")
            with open(manifest_filepath, "r", encoding="utf-8") as f:
                try:
                    chapter_manifest = json.load(f)
                except json.JSONDecodeError:
                    print("Warning: Manifest file is corrupted. Starting from scratch.")
                    chapter_manifest = []

            if chapter_manifest:
                last_chapter = chapter_manifest[-1]
                start_chapter_count = last_chapter["number"]

                # To resume, we need the URL of the last successfully scraped page.
                # Let's add the URL to the manifest for future reliability.
                if "url" not in last_chapter:
                    print(
                        "Warning: Older manifest format. Cannot reliably resume. Consider restarting."
                    )
                    return

                last_chapter_url = last_chapter["url"]
                print(
                    f"Last saved chapter was #{start_chapter_count}: {last_chapter['title']}"
                )
                print(
                    f"Re-fetching last chapter's page to find the 'Next' link: {last_chapter_url}"
                )

                try:
                    last_page = session.get(last_chapter_url)
                    last_page_soup = BeautifulSoup(last_page.content, "html.parser")
                    next_link_element = last_page_soup.find(id="next_chap")
                    if next_link_element and "disabled" not in next_link_element.get(
                        "class", []
                    ):
                        current_chapter_url = next_link_element.get("href")
                        print(f"Resuming download from: {current_chapter_url}")
                    else:
                        print(
                            "Last saved chapter was the final chapter. Download is complete."
                        )
                        return  # Exit, nothing more to do
                except Exception as e:
                    print(f"Could not fetch last chapter page to resume. Error: {e}")
                    return
            else:
                print("Manifest is empty. Starting from the beginning.")

        if not current_chapter_url:
            print("Starting download from the beginning.")
            first_chapter_span = soup.select_one(
                "span.nchr-text[data-novel_id][data-chapter_id]"
            )
            novel_id = first_chapter_span.get("data-novel_id")
            chapter_id = first_chapter_span.get("data-chapter_id")
            current_chapter_url = f"https://novelbin.com/b/{novel_id}/{chapter_id}"

        chapter_count = start_chapter_count

        while current_chapter_url:
            if not current_chapter_url.startswith("http"):
                current_chapter_url = urljoin(novel_url, current_chapter_url)

            print(f"  Downloading Chapter {chapter_count + 1}...")
            try:
                chapter_page = session.get(current_chapter_url)
                chapter_page.raise_for_status()
                chapter_soup = BeautifulSoup(chapter_page.content, "html.parser")

                title_element = chapter_soup.find("a", class_="chr-title")
                chapter_title = (
                    title_element.get("title", f"Chapter {chapter_count + 1}").strip()
                    if title_element
                    else f"Chapter {chapter_count + 1}"
                )

                safe_chapter_title = sanitize_filename(chapter_title)
                chapter_filename = (
                    f"{str(chapter_count + 1).zfill(4)}-{safe_chapter_title}.txt"
                )
                chapter_filepath = os.path.join(raw_folder, chapter_filename)

                content_div = chapter_soup.find(id="chr-content")
                if content_div:
                    cleaned_text = basic_clean_text(
                        content_div.get_text(separator="\n")
                    )
                    with open(chapter_filepath, "w", encoding="utf-8") as f:
                        f.write(cleaned_text)

                    # Add to manifest, including the URL for future resumes
                    chapter_manifest.append(
                        {
                            "number": chapter_count + 1,
                            "title": chapter_title,
                            "file": chapter_filename,
                            "url": current_chapter_url,  # IMPORTANT FOR RESUMING
                        }
                    )

                    # Save the manifest after every successful chapter download
                    with open(manifest_filepath, "w", encoding="utf-8") as f:
                        json.dump(chapter_manifest, f, indent=2)

                next_link_element = chapter_soup.find(id="next_chap")
                current_chapter_url = (
                    next_link_element.get("href")
                    if next_link_element
                    and "disabled" not in next_link_element.get("class", [])
                    else None
                )
                time.sleep(random.uniform(1.2, 2.5))  # Randomized delay
            except curl_requests.errors.RequestsError as e:
                print(
                    f"    ERROR on chapter {chapter_count + 1}: {e}. Stopping download."
                )
                break

            chapter_count += 1

        print(
            f"--- Download Complete: Total scraped chapters in this run: {chapter_count - start_chapter_count} ---"
        )

    except Exception as e:
        print(f"Download action failed: {e}")


def action_llm_process(novel_folder):
    """Action: Processes a downloaded novel with the LLM."""
    print(f"--- Action: LLM Process ---")
    print(f"Processing novel in folder: '{novel_folder}'")

    if not initialize_llm():
        return

    raw_folder = os.path.join(novel_folder, "raw_chapters")
    llm_folder = os.path.join(novel_folder, "llm_chapters")
    os.makedirs(llm_folder, exist_ok=True)

    if not os.path.isdir(raw_folder):
        print(f"Error: Raw chapters folder not found at '{raw_folder}'")
        return

    raw_files = sorted([f for f in os.listdir(raw_folder) if f.endswith(".txt")])
    total_files = len(raw_files)

    for i, filename in enumerate(raw_files):
        # Check if the file has already been processed to allow resuming
        llm_filepath = os.path.join(llm_folder, filename)
        if os.path.exists(llm_filepath):
            print(
                f"  Skipping file {i + 1}/{total_files} (already processed): {filename}"
            )
            continue

        print(f"  Processing file {i + 1}/{total_files}: {filename}")
        with open(os.path.join(raw_folder, filename), "r", encoding="utf-8") as f:
            raw_text = f.read()

        text_chunks = chunk_text(raw_text)
        edited_chunks = [llm_edit_text(chunk) for chunk in text_chunks]
        final_text = "\n\n".join(edited_chunks)

        with open(llm_filepath, "w", encoding="utf-8") as f:
            f.write(final_text)

    print(f"--- LLM Processing Complete for {novel_folder} ---")


def llm_edit_text(text_chunk):
    if not text_chunk.strip():
        return ""
    if not llm_model:
        raise ConnectionError("LLM not initialized.")
    try:
        full_prompt = EDITING_PROMPT.format(text_chunk)
        response = llm_model.generate_content(
            full_prompt, request_options={"timeout": 120}
        )
        time.sleep(1.5)
        return response.text if response.parts else text_chunk
    except Exception as e:
        print(f"    > LLM ERROR: {e}. Returning original chunk.")
        return text_chunk


def action_update_git():
    """Action: Updates manifests and pushes all changes to Git."""
    print("--- Action: Update and Push ---")
    print("Updating main manifest...")
    novels = [
        d
        for d in os.listdir(REPO_PATH)
        if os.path.isdir(os.path.join(REPO_PATH, d))
        and not d.startswith((".", "venv"))
        and os.path.exists(os.path.join(REPO_PATH, d, "manifest.json"))
    ]
    with open(os.path.join(REPO_PATH, "manifest.json"), "w") as f:
        json.dump(novels, f, indent=2)
    print("Main manifest updated.")

    try:
        repo = git.Repo(REPO_PATH)
        if not repo.is_dirty(untracked_files=True):
            print("No changes to commit.")
            return
        print("Adding changes to Git...")
        repo.git.add(A=True)
        commit_message = (
            f"Automated novel update - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        repo.index.commit(commit_message)
        print(f"Committed changes: '{commit_message}'")
        origin = repo.remote(name="origin")
        print("Pushing to remote...")
        origin.push()
        print("Push successful.")
    except Exception as e:
        print(f"Git operation failed: {e}")


# --- CLI SETUP ---


def main():
    parser = argparse.ArgumentParser(
        description="A CLI tool to download and process web novels."
    )
    subparsers = parser.add_subparsers(
        dest="action", required=True, help="Available actions"
    )

    parser_download = subparsers.add_parser(
        "download",
        help="Download a novel's raw text from a URL. Resumes if folder exists.",
    )
    parser_download.add_argument(
        "url", type=str, help="The URL of the novel's main page."
    )

    parser_llm = subparsers.add_parser(
        "llm",
        help="Process a previously downloaded novel with the LLM. Resumes if partially complete.",
    )
    parser_llm.add_argument(
        "folder", type=str, help="The name of the novel's folder to process."
    )

    parser_update = subparsers.add_parser(
        "update", help="Update manifests and push all changes to the Git repository."
    )

    args = parser.parse_args()

    if args.action == "download":
        action_download(args.url)
    elif args.action == "llm":
        action_llm_process(args.folder)
    elif args.action == "update":
        action_update_git()


if __name__ == "__main__":
    main()
