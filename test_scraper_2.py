# test_scraper.py (Corrected and Improved Version)

import unittest
from unittest.mock import patch, MagicMock
import scraper  # Import our main script


class TestHelperFunctions(unittest.TestCase):
    # This test does NOT need the LLM. It runs completely on its own.
    def test_sanitize_filename(self):
        """Tests that invalid characters are removed from filenames."""
        self.assertEqual(scraper.sanitize_filename("A*B/C:D<E>F|G?H"), "ABCDEFGH")
        self.assertEqual(scraper.sanitize_filename("Valid-Name_123"), "Valid-Name_123")

    # This test also does NOT need the LLM.
    def test_basic_clean_text(self):
        """Tests the basic regex-based text cleaning."""
        # Test case 1
        text1 = "Hello World. This chapter is updated by novelbin.com"
        expected1 = "Hello World."
        self.assertEqual(scraper.basic_clean_text(text1), expected1)

        # Test case 2 (The one that was failing)
        text2 = "Read latest Chapters at novelbin.com Only. The story begins."
        expected2 = "The story begins."
        self.assertEqual(scraper.basic_clean_text(text2), expected2)


# A separate class for tests that require mocking the LLM
class TestLLMFunctions(unittest.TestCase):
    # The @patch decorator now correctly applies ONLY to the tests in this class.
    # It replaces 'scraper.llm_model' with a mock for the duration of each test.
    @patch("scraper.llm_model")
    def test_llm_edit_text_success(self, mock_llm_model):
        """Tests the LLM editing function's success path."""
        # Configure the mock to simulate a successful API call
        mock_response = MagicMock()
        mock_response.text = "This is the corrected text."
        mock_response.parts = [mock_response.text]
        mock_llm_model.generate_content.return_value = mock_response

        original_text = "This is the incorect text."
        edited_text = scraper.llm_edit_text(original_text)

        mock_llm_model.generate_content.assert_called_once()
        self.assertEqual(edited_text, "This is the corrected text.")

    @patch("scraper.llm_model")
    def test_llm_edit_text_api_failure(self, mock_llm_model):
        """Tests that the original text is returned if the LLM API call fails."""
        # Configure the mock to simulate an API error
        mock_llm_model.generate_content.side_effect = Exception("API limit reached")

        original_text = "This text will be returned as-is."
        # We need to explicitly call the function to test it
        edited_text = scraper.llm_edit_text(original_text)

        # Assert that the function returns the original text upon failure
        self.assertEqual(edited_text, original_text)
        # Also assert that the mock was actually called
        mock_llm_model.generate_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
