# labalaba_baca

# Create a virtual environment using uv
uv venv

# Activate the environment
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install packages using uv (it's much faster!)
# We add google-generativeai for the LLM
uv pip install requests beautifulsoup4 GitPython google-generativeai
