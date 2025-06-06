# test_api_httpx.py
import os
import httpx
import json

# --- Configuration ---
# Your custom environment variable name
API_KEY_ENV_VARIABLE = "KUCING_NAKAL_GOOGLE_API_KEY"

# The Google Gemini Pro API endpoint URL
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"
LIST_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

print("--- Gemini API Connection Test (using httpx) ---")

# --- 1. Load the API key from the environment variable ---
api_key = os.getenv(API_KEY_ENV_VARIABLE)

if not api_key:
    print(f"\n[FAILURE] ❌ Environment variable '{API_KEY_ENV_VARIABLE}' not found.")
    print("Please make sure you have set it correctly by running:")
    print(f'  export {API_KEY_ENV_VARIABLE}="YOUR_API_KEY_HERE"')
    exit()

print(f"\n[SUCCESS] ✅ Found API key in environment variable '{API_KEY_ENV_VARIABLE}'.")

# --- 2. Prepare the HTTP request ---
# The headers must include the content type and your API key
headers = {
    "Content-Type": "application/json",
}

# The parameters must include the key
params = {
    "key": api_key,
}

# The data payload contains the prompt for the model
payload = {
    "contents": [
        {
            "parts": [
                {
                    "text": "In one short, friendly sentence, tell me what a Large Language Model is."
                }
            ]
        }
    ]
}

print("\nSending request to list models...")

# --- 3. Send the request using httpx ---
try:
    with httpx.Client(timeout=20.0) as client:
        # We use a GET request for listing resources
        response = client.get(LIST_MODELS_URL, params=params)
        response.raise_for_status()

        response_data = response.json()
        models = response_data.get("models", [])

        if not models:
            print("\n[WARNING] ⚠️ No models were returned. Check your API permissions.")
        else:
            print("\n--- Available Models and Supported Methods ---")
            for model in models:
                # Extract the important details for each model
                display_name = model.get("displayName", "N/A")
                full_name = model.get("name", "N/A")
                methods = model.get("supportedGenerationMethods", ["N/A"])

                print(f"\nDisplay Name: {display_name}")
                print(f"  > Full API Name: {full_name}")
                print(f"  > Supported Methods: {methods}")

                # Highlight the models that we can actually use for our scraper
                if "generateContent" in methods:
                    print("  > ✅ This model CAN be used for our scraper.")
                else:
                    print("  > ❌ This model CANNOT be used for our scraper.")
            print("\n--------------------------------------------")

except httpx.HTTPStatusError as e:
    print(
        f"\n[FAILURE] ❌ An HTTP error occurred: Status Code {e.response.status_code}"
    )
    print("Please check your API key and permissions.")
    print(f"Full error response: {e.response.text}")
except httpx.RequestError as e:
    print(f"\n[FAILURE] ❌ A network request error occurred: {e}")

print("\nPreparing to send a direct HTTP request to the Gemini API...")

# --- 3. Send the request using httpx ---
try:
    with httpx.Client(timeout=30.0) as client:
        # We use a POST request as required by the API
        response = client.post(
            GEMINI_API_URL,
            headers=headers,
            params=params,
            json=payload,  # httpx automatically handles converting the dict to a JSON string
        )

        # raise_for_status() will throw an exception for 4xx or 5xx errors (like 403 Forbidden)
        response.raise_for_status()

        # If we get here, the request was successful (status code 200 OK)
        print("\n[SUCCESS] ✅ API request was successful (Status Code 200).")

        # --- 4. Parse and print the response ---
        response_data = response.json()

        # Safely extract the text from the nested JSON structure
        try:
            generated_text = response_data["candidates"][0]["content"]["parts"][0][
                "text"
            ]
            print("\n--- API Response ---")
            print(generated_text.strip())
            print("--------------------\n")
            print("Congratulations! Your API key is working correctly.")
        except (KeyError, IndexError) as e:
            print(f"\n[WARNING] ⚠️ Could not parse the text from the API response: {e}")
            print("Full response JSON:")
            print(json.dumps(response_data, indent=2))

except httpx.HTTPStatusError as e:
    # This block catches specific HTTP errors like 400, 403, 429, etc.
    print(
        f"\n[FAILURE] ❌ An HTTP error occurred: Status Code {e.response.status_code}"
    )
    print(
        "This often means the API key is invalid, expired, or the API is not enabled."
    )
    # Print the error details from the API response if available
    try:
        error_details = e.response.json()
        print("\n--- Error Details from API ---")
        print(json.dumps(error_details, indent=2))
        print("------------------------------")
    except json.JSONDecodeError:
        print("Could not parse error details from the response body.")
        print(f"Raw response body: {e.response.text}")

except httpx.RequestError as e:
    # This block catches network-level errors (DNS, connection timeout, etc.)
    print(f"\n[FAILURE] ❌ A network request error occurred: {e}")
    print("Check your internet connection and if the URL is correct.")

except Exception as e:
    # Catch any other unexpected errors
    print(f"\n[FAILURE] ❌ An unexpected error occurred: {e}")
