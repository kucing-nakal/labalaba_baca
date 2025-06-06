import unittest
from unittest.mock import patch, MagicMock
import scraper  # Import our main script to test its functions


class TestScraperFunctions(unittest.TestCase):
    def test_sanitize_filename(self):
        """Tests that invalid characters are removed from filenames."""
        self.assertEqual(scraper.sanitize_filename("A*B/C:D<E>F|G?H"), "ABCDEFGH")
        self.assertEqual(scraper.sanitize_filename("Valid-Name_123"), "Valid-Name_123")
        self.assertEqual(scraper.sanitize_filename(""), "")

    def test_basic_clean_text(self):
        """Tests the basic regex-based text cleaning."""
        text = "Hello World. This chapter is updated by novelbin.com"
        expected = "Hello World."
        self.assertEqual(scraper.basic_clean_text(text), expected)

        text = "Read latest Chapters at novelbin.com Only. The story begins."
        expected = "The story begins."
        self.assertEqual(scraper.basic_clean_text(text), expected)

    # We use `@patch` to replace the real LLM model with a "mock" object during this test.
    # This lets us test our function's logic without actually calling the Google API.
    @patch("scraper.llm_model")
    def test_llm_edit_text_success(self, mock_llm_model):
        """Tests the LLM editing function's success path using a mock API call."""
        # Configure the mock object to behave like the real one
        mock_response = MagicMock()
        mock_response.text = "This is the corrected text."
        mock_response.parts = [mock_response.text]  # Ensure 'parts' is not empty
        mock_llm_model.generate_content.return_value = mock_response

        # The text we are "sending" to the mock LLM
        original_text = "This is the incorect text."
        edited_text = scraper.llm_edit_text(original_text)

        # Assert that our function called the mock LLM correctly
        mock_llm_model.generate_content.assert_called_once()

        # Assert that our function returned the text from the mock LLM
        self.assertEqual(edited_text, "This is the corrected text.")

    @patch("scraper.llm_model")
    def test_llm_edit_text_api_failure(self, mock_llm_model):
        """Tests that the original text is returned if the LLM API call fails."""
        # Configure the mock to raise an exception, simulating an API error
        mock_llm_model.generate_content.side_effect = Exception("API limit reached")

        original_text = "This text will be returned as-is."
        edited_text = scraper.llm_edit_text(original_text)

        # Assert that the function returns the original text upon failure
        self.assertEqual(edited_text, original_text)


if __name__ == "__main__":
    unittest.main()
