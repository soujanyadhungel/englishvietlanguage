import csv
import os
import requests
import logging
from googletrans import Translator
import time
from typing import List, Dict, Optional
from google.cloud import translate_v2 as translate
from google.cloud import texttospeech
import base64

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VocabularyService:
    """Manages vocabulary data, including CRUD operations, definitions, translations, and audio generation."""
    def __init__(self, csv_file='vocabulary.csv'):
        """Initializes the VocabularyService.

        Args:
            csv_file (str): The path to the CSV file used for storing vocabulary data.
                          Defaults to 'vocabulary.csv'.
        """
        self.csv_file = csv_file
        self.translator = Translator()  # googletrans Translator for fallback
        self.headers = ['English Word', 'English Definition', 'English Example', 'Vietnamese Definition', 'Vietnamese Example']
        
        # Set actual API keys
        self.api_key = "AIzaSyB6Wrr50VOchRDtWYHl4SIQ5LxtX1Ez_tY"  # Google Cloud API key
        self.elevenlabs_api_key = "sk_ff8ff56d2f379773d4a974f3e8a24ae794cfda35ca059148"  # ElevenLabs API key
        
        if not self.api_key:
            logging.warning("Google Cloud API key not set. Google Cloud services (Translate, TTS) will not be available.")
        if not self.elevenlabs_api_key:
            logging.warning("ElevenLabs API key not set. ElevenLabs TTS will not be available.")
        
        self._ensure_csv_exists() # Ensure CSV file is present with headers.
    
    def _ensure_csv_exists(self):
        """Ensures the CSV file exists and has the correct headers.
        
        If the CSV file specified in `self.csv_file` does not exist,
        it creates the file and writes the headers defined in `self.headers`.
        """
        if not os.path.exists(self.csv_file):
            try:
                with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(self.headers)
                logging.info(f"Created new CSV file with headers: {self.csv_file}")
            except IOError as e:
                logging.error(f"Error creating CSV file {self.csv_file}: {e}")
                # Depending on the application's needs, this might raise an exception
                # or attempt to handle the error in another way.
    
    def get_csv_path(self) -> str:
        """Returns the absolute path to the vocabulary CSV file."""
        return os.path.abspath(self.csv_file)
    
    def get_english_definition(self, word: str) -> Optional[Dict[str, str]]:
        """Fetches or generates an English definition and example sentence for a given word.

        It first attempts to use the Free Dictionary API (https://api.dictionaryapi.dev/) for a real definition and example.
        If that fails, it falls back to the Google Cloud Translation API by translating Vietnamese prompts for definition and example back to English.

        Args:
            word (str): The English word for which to get the definition and example.

        Returns:
            Optional[Dict[str, str]]: A dictionary with 'definition' and 'example' keys
                                      if successful, otherwise None.
        """
        if not word:
            logging.warning("get_english_definition called with an empty word."); logging.getLogger().handlers[0].flush()
            return None

        # Attempt 1: Use DictionaryAPI for definition and example
        logging.info(f"[get_english_definition] Trying DictionaryAPI for '{word}'"); logging.getLogger().handlers[0].flush()
        dict_result = self._get_fallback_definition(word)
        if dict_result and dict_result.get('definition') and dict_result.get('example'):
            logging.info(f"[get_english_definition] Got from DictionaryAPI: def='{dict_result['definition']}', ex='{dict_result['example']}'"); logging.getLogger().handlers[0].flush()
            return dict_result
        else:
            logging.warning(f"[get_english_definition] DictionaryAPI failed for '{word}'. Trying Google Cloud fallback."); logging.getLogger().handlers[0].flush()

        # Attempt 2: Google Cloud Translation API fallback
        if self.api_key:
            try:
                logging.info(f"[get_english_definition] Attempting Google Cloud fallback for '{word}'"); logging.getLogger().handlers[0].flush()
                vietnamese_definition_prompt = f"Định nghĩa chi tiết và rõ ràng của từ tiếng Anh '{word}' dành cho người học ngôn ngữ."
                vietnamese_example_prompt = f"Một câu ví dụ điển hình sử dụng từ tiếng Anh '{word}' trong ngữ cảnh thực tế."
                definition_en = self.translate_text_with_google(vietnamese_definition_prompt, target_language='en')
                example_en = self.translate_text_with_google(vietnamese_example_prompt, target_language='en')
                logging.info(f"[get_english_definition] Google returned: def='{definition_en}', ex='{example_en}'"); logging.getLogger().handlers[0].flush()
                if definition_en and example_en:
                    clean_definition = definition_en.replace(f"Detailed and clear definition of the English word '{word}' for language learners.", "").strip()
                    clean_example = example_en.replace(f"A typical example sentence using the English word '{word}' in a real context.", "").strip()
                    if clean_definition.startswith("Define the English word"):
                        clean_definition = clean_definition.replace("Define the English word", "").replace(f"'{word}'", "").strip()
                    if clean_definition.startswith("detailed and clear"):
                        clean_definition = f"A word that means: {clean_definition.split('detailed and clear')[-1].strip()}"
                    elif not clean_definition.startswith(("A ", "An ", "The ", "To ")) and clean_definition:
                        clean_definition = f"To {clean_definition.lower()}" if clean_definition[0].islower() else clean_definition
                    if clean_example.startswith("Give a clear example sentence using the English word"):
                        clean_example = clean_example.replace("Give a clear example sentence using the English word", "").replace(f"'{word}'", word).strip()
                    if not any(w.lower() in clean_example.lower() for w in word.split()):
                        clean_example = f"{word.capitalize()}: {clean_example}" if clean_example else f"Example featuring {word}."
                    logging.info(f"[get_english_definition] Cleaned (Google fallback): def='{clean_definition}', ex='{clean_example}'"); logging.getLogger().handlers[0].flush()
                    return {
                        'definition': clean_definition or f"Definition for {word}",
                        'example': clean_example or f"Example for {word}."
                    }
                else:
                    logging.warning(f"[get_english_definition] Google Cloud fallback failed for '{word}'."); logging.getLogger().handlers[0].flush()
            except Exception as e:
                logging.error(f"[get_english_definition] Google Cloud error for '{word}': {e}"); logging.getLogger().handlers[0].flush()
        logging.error(f"[get_english_definition] No definition/example found for '{word}'."); logging.getLogger().handlers[0].flush()
        return None
    
    def translate_text_with_google(self, text: str, target_language: str = 'en', source_language: Optional[str] = None) -> str:
        """Translates text using the Google Cloud Translation API (REST).

        Requires `GOOGLE_CLOUD_API_KEY` to be set in the environment.

        Args:
            text (str): The text to translate.
            target_language (str): The target language code (e.g., 'en', 'vi').
            source_language (Optional[str]): The source language code. If None, Google attempts to detect it.

        Returns:
            str: The translated text, or an empty string if translation fails.
        """
        if not self.api_key:
            logging.error("translate_text_with_google called but GOOGLE_CLOUD_API_KEY is not set.")
            return ""
        if not text:
            logging.warning("translate_text_with_google called with empty text.")
            return ""
            
        url = f"https://translation.googleapis.com/language/translate/v2?key={self.api_key}"
        payload = {
            'q': text,
            'target': target_language,
            'format': 'text'
        }
        if source_language:
            payload['source'] = source_language
            
        try:
            response = requests.post(url, data=payload, timeout=10) # Increased timeout for robustness
            response.raise_for_status() # Raise HTTPError for bad responses (4XX or 5XX)
            
            result = response.json()
            if 'data' in result and 'translations' in result['data'] and result['data']['translations']:
                translated_text = result['data']['translations'][0]['translatedText']
                logging.info(f"Google Cloud Translation successful for text: '{text[:30]}...' -> '{translated_text[:30]}...'")
                return translated_text
            else:
                logging.error(f"Google Cloud Translation API call succeeded but response format was unexpected: {result}")
                return ""
        except requests.exceptions.RequestException as e:
            logging.error(f"Google Cloud Translation API request failed: {e}")
            return ""
        except Exception as e:
            logging.error(f"An unexpected error occurred in translate_text_with_google: {e}")
            return ""
    
    def _get_fallback_definition(self, word: str) -> Optional[Dict[str, str]]:
        """Fallback method to get word definition and example using the DictionaryAPI.dev.

        This method is used if the primary Google Cloud-based definition generation fails.

        Args:
            word (str): The English word.

        Returns:
            Optional[Dict[str, str]]: Dictionary with 'definition' and 'example', or None if failed.
        """
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower().strip()}"
            response = requests.get(url, timeout=10) # Increased timeout
            response.raise_for_status() # Checks for HTTP errors
            
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                entry = data[0]
                definition = "No definition available."
                example = "No example sentence available."
                
                if 'meanings' in entry and entry['meanings']:
                    for meaning in entry['meanings']:
                        if 'definitions' in meaning and meaning['definitions']:
                            def_data = meaning['definitions'][0]
                            definition = def_data.get('definition', definition)
                            example = def_data.get('example', example) # Example might be directly under definition
                            if example != "No example sentence available.": break # Found a good definition and example
                    # If no example found with a definition, check phonetic examples
                    if example == "No example sentence available." and 'phonetics' in entry and entry['phonetics']:
                        for phonetic_info in entry['phonetics']:
                            if phonetic_info.get('text') and phonetic_info.get('audio'): # often example might be here by mistake of API
                                # This logic is a bit speculative as API structure varies.
                                # Sometimes example-like text can be in phonetics. This is a heuristic.
                                pass # Decided against using phonetic text as example as it is unreliable
                
                logging.info(f"Successfully fetched definition for '{word}' using DictionaryAPI.dev.")
                return {'definition': definition, 'example': example}
            else:
                logging.warning(f"DictionaryAPI.dev: No data found or unexpected format for '{word}'. Response: {data}")
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logging.warning(f"DictionaryAPI.dev: Word '{word}' not found (404). Details: {e}")
            else:
                logging.error(f"DictionaryAPI.dev: HTTP error for '{word}'. Status: {e.response.status_code}. Details: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"DictionaryAPI.dev: Request failed for '{word}'. Details: {e}")
            return None
        except Exception as e:
            logging.error(f"DictionaryAPI.dev: Unexpected error for '{word}': {e}")
            return None
    
    def translate_to_vietnamese(self, text: str) -> str:
        """Translates English text to Vietnamese.

        Prioritizes Google Cloud Translation API if `GOOGLE_CLOUD_API_KEY` is set.
        Falls back to the `googletrans` library if the API key is not available or the API call fails.

        Args:
            text (str): The English text to translate.

        Returns:
            str: The translated Vietnamese text, or a failure message if all attempts fail.
        """
        if not text:
            logging.warning("translate_to_vietnamese called with empty text."); logging.getLogger().handlers[0].flush()
            return "(No text provided for translation)"

        # Attempt 1: Google Cloud Translation API
        if self.api_key:
            translated_text = self.translate_text_with_google(text, target_language='vi', source_language='en')
            logging.info(f"[translate_to_vietnamese] Google returned: '{translated_text}' for '{text}'"); logging.getLogger().handlers[0].flush()
            if translated_text:
                return translated_text
            logging.warning(f"[translate_to_vietnamese] Google Cloud failed for '{text[:30]}...'. Trying fallback."); logging.getLogger().handlers[0].flush()

        # Attempt 2: Fallback to googletrans library
        try:
            logging.info(f"[translate_to_vietnamese] Falling back to googletrans for '{text[:30]}...'"); logging.getLogger().handlers[0].flush()
            time.sleep(0.2)
            result = self.translator.translate(text, src='en', dest='vi')
            if result and result.text:
                logging.info(f"[translate_to_vietnamese] googletrans returned: '{result.text}'"); logging.getLogger().handlers[0].flush()
                return result.text
            else:
                logging.error(f"[translate_to_vietnamese] googletrans fallback failed for '{text[:30]}...': No text returned."); logging.getLogger().handlers[0].flush()
                return f"[googletrans fallback error: No text] {text}"
        except Exception as fallback_error:
            logging.error(f"[translate_to_vietnamese] googletrans fallback translation failed for '{text[:30]}...': {fallback_error}"); logging.getLogger().handlers[0].flush()
            return f"[Translation failed for: {text[:30]}...]"
    
    def get_pronunciation_guide(self, text: str) -> str:
        """Generates a *very* basic pseudo-phonetic pronunciation guide for English text.

        This is a simplistic implementation and not a proper phonetic transcription.
        It applies a few common English digraph to phoneme mappings.

        Args:
            text (str): The English text.

        Returns:
            str: A string representing a simplified pronunciation (e.g., "/həˈloʊ/").
        """
        if not text:
            return "//"
        try:
            # This is a placeholder for a more sophisticated phonetic guide.
            # For a real app, consider using a dedicated phonetic library or API.
            import re # Import locally as it's only used here.
            
            text_lower = text.lower().strip()
            # More comprehensive map - still very basic
            pronunciation_map = {
                '(^|\s)th': 'θ', ' th': ' ð', # Simplified th
                'ch': 'tʃ',
                'sh': 'ʃ',
                'ph': 'f',
                'tion': 'ʃən', 'sion': 'ʒən', 'cious': 'ʃəs', 'tious': 'ʃəs',
                'ough': 'ɔːf', # Highly variable, this is one common pronunciation (e.g. tough, rough)
                'augh': 'ɔːf',
                'eigh': 'eɪ', 'igh': 'aɪ', 'ight': 'aɪt',
                'oo': 'uː', # as in "food"
                'ea': 'iː', # as in "read"
                'ai': 'eɪ', # as in "rain"
                'kn': 'n', 'gn': 'n', # silent k, g
                'ps': 's', # silent p
            }
            
            pronunciation = text_lower
            for pattern, replacement in pronunciation_map.items():
                pronunciation = re.sub(pattern, replacement, pronunciation)
            
            # Rudimentary stress marking for single words (very heuristic)
            if ' ' not in pronunciation and len(pronunciation) > 4:
                pronunciation = f"'{pronunciation}" # Stress on first syllable approximation
            
            return f"/{pronunciation}/"
            
        except Exception as e:
            logging.error(f"Pronunciation guide generation failed for text '{text}': {e}")
            return f"/{text.lower()}/ (Error in generation)"
    
    def generate_audio(self, text: str, language: str, service: str = 'google') -> Optional[str]:
        """Generates audio using the specified TTS service and returns base64 encoded MP3 audio.

        Args:
            text (str): The text to synthesize.
            language (str): The language code ('en' for English, 'vi' for Vietnamese).
            service (str): 'google', 'elevenlabs', or 'browser'.

        Returns:
            Optional[str]: Base64 encoded MP3 audio content as a string, or None if generation fails or is browser.
        """
        logging.info(f"Generating audio for text: '{text[:30]}...' in language '{language}' using service '{service}'")
        
        if service == 'browser':
            logging.info("Using browser TTS - no audio generation needed")
            return None
            
        if service == 'elevenlabs':
            if not self.elevenlabs_api_key:
                logging.error("ElevenLabs API key not set")
                return None
                
            if not text:
                logging.error("Empty text provided for ElevenLabs TTS")
                return None
                
            try:
                voice_id = 'HDA9tsk27wYi3uq0fPcK' if language.lower().startswith('en') else 'ueSxRO0nLF1bj93J2hVt'
                logging.info(f"Using ElevenLabs voice ID: {voice_id}")
                
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    'xi-api-key': self.elevenlabs_api_key,
                    'Content-Type': 'application/json',
                }
                payload = {
                    'text': text,
                    'voice_settings': {
                        'stability': 0.5,
                        'similarity_boost': 0.5
                    }
                }
                
                logging.info(f"Making ElevenLabs API request to {url}")
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                response.raise_for_status()
                
                audio_bytes = response.content
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                logging.info("ElevenLabs TTS successful")
                return audio_b64
                
            except Exception as e:
                logging.error(f"ElevenLabs TTS error: {str(e)}")
                return None
                
        # Google TTS
        if not self.api_key:
            logging.error("Google Cloud API key not set")
            return None
            
        if not text:
            logging.error("Empty text provided for Google TTS")
            return None
            
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.api_key}"
        voice_config = {}
        
        if language.lower().startswith('vi'):
            voice_config = {
                'languageCode': 'vi-VN',
                'name': 'vi-VN-Standard-D',
            }
        elif language.lower().startswith('en'):
            voice_config = {
                'languageCode': 'en-US',
                'name': 'en-US-Standard-C',
            }
        else:
            logging.warning(f"Unsupported language '{language}' - defaulting to en-US")
            voice_config = {'languageCode': 'en-US', 'name': 'en-US-Standard-C'}
            
        logging.info(f"Using Google TTS voice config: {voice_config}")
        
        payload = {
            'input': {'text': text},
            'voice': voice_config,
            'audioConfig': {
                'audioEncoding': 'MP3',
                'speakingRate': 0.95
            }
        }
        
        try:
            logging.info(f"Making Google Cloud TTS API request")
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            audio_content = result.get('audioContent')
            
            if audio_content:
                logging.info("Google Cloud TTS successful")
                return audio_content
            else:
                logging.error(f"No audioContent in response: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Google Cloud TTS API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Response text: {e.response.text}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in Google TTS: {str(e)}")
            return None
    
    def add_word(self, english_word: str) -> bool:
        """Adds a new English word to the vocabulary CSV file.

        This involves fetching its English definition/example, translating them to Vietnamese,
        and then writing the new entry to the CSV.

        Note: This method itself does not perform a duplicate check. Duplicate checking is expected
        to be handled by the calling code (e.g., in the Flask app route) using `word_exists()`.

        Args:
            english_word (str): The English word to add.

        Returns:
            bool: True if the word was successfully added (i.e., definition found and CSV written),
                  False otherwise (e.g., definition not found, or error during CSV write).
        """
        if not english_word or not english_word.strip():
            logging.warning("add_word called with an empty or whitespace-only word.")
            return False
        
        english_word = english_word.strip() # Ensure no leading/trailing whitespace

        try:
            logging.info(f"Attempting to add word: '{english_word}'")
            definition_data = self.get_english_definition(english_word)
            
            if not definition_data or not definition_data.get('definition'):
                logging.warning(f"No definition found for word: '{english_word}'. Word not added.")
                return False
            
            english_definition = definition_data['definition']
            english_example = definition_data.get('example', "No example provided.") # Ensure example has a default
            
            vietnamese_definition = self.translate_to_vietnamese(english_definition)
            vietnamese_example = self.translate_to_vietnamese(english_example)
            
            # Check if translations failed and provide placeholders
            if vietnamese_definition.startswith("[Translation failed") or vietnamese_definition.startswith("[googletrans fallback error"):
                logging.warning(f"Failed to translate definition for '{english_word}'. Using placeholder.")
                # Keep the English one or use a placeholder, decide based on desired behavior
            if vietnamese_example.startswith("[Translation failed") or vietnamese_example.startswith("[googletrans fallback error"):
                logging.warning(f"Failed to translate example for '{english_word}'. Using placeholder.")

            new_row = [
                english_word,
                english_definition,
                english_example,
                vietnamese_definition,
                vietnamese_example
            ]
            
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(new_row)
            
            logging.info(f"Successfully added word '{english_word}' to CSV: {self.csv_file}")
            return True
            
        except IOError as e:
            logging.error(f"IOError adding word '{english_word}' to CSV {self.csv_file}: {e}")
            return False
        except Exception as e:
            # Catch any other unexpected errors during the add_word process
            logging.error(f"Unexpected error adding word '{english_word}': {e}")
            return False
    
    def get_all_vocabulary(self) -> List[Dict[str, str]]:
        """Retrieves all vocabulary entries from the CSV file.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, where each dictionary
                                  represents a vocabulary entry (row from CSV).
                                  Returns an empty list if the file doesn't exist or is empty,
                                  or if an error occurs.
        """
        if not os.path.exists(self.csv_file):
            logging.warning(f"Vocabulary CSV file not found: {self.csv_file}. Returning empty list.")
            self._ensure_csv_exists() # Attempt to create it if missing
            return [] # Still return empty as it would have just been created
            
        vocabulary = []
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                # Ensure headers match expected, otherwise DictReader might behave unexpectedly
                if reader.fieldnames != self.headers:
                    logging.warning(f"CSV headers mismatch in {self.csv_file}. Expected: {self.headers}, Found: {reader.fieldnames}. Data might be skewed.")
                    # Optionally, could try to process based on found headers or return error/empty
                for row in reader:
                    vocabulary.append(row)
            logging.debug(f"Loaded {len(vocabulary)} vocabulary entries from {self.csv_file}")
            return vocabulary
        except FileNotFoundError:
            # This case should ideally be caught by the os.path.exists check above,
            # but as a safeguard / if _ensure_csv_exists fails silently.
            logging.error(f"FileNotFoundError for {self.csv_file} in get_all_vocabulary despite initial check.")
            return []
        except Exception as e:
            logging.error(f"Error reading vocabulary from CSV {self.csv_file}: {e}")
            return [] # Return empty list on other errors
    
    def word_exists(self, word: str) -> bool:
        """Checks if a word (case-insensitive) already exists in the vocabulary.

        Args:
            word (str): The English word to check.

        Returns:
            bool: True if the word exists, False otherwise.
        """
        if not word:
            return False
        try:
            vocabulary = self.get_all_vocabulary()
            word_lower = word.lower().strip()
            return any(entry.get('English Word', '').lower() == word_lower for entry in vocabulary)
        except Exception as e:
            # This might catch errors from get_all_vocabulary if it has issues
            logging.error(f"Error checking if word '{word}' exists: {e}")
            return False # Default to false on error to be safe (e.g. allow add attempt)
    
    def search_vocabulary(self, query: str) -> List[Dict[str, str]]:
        """Searches vocabulary entries by a query string (case-insensitive).

        The search query is matched against the 'English Word', 'English Definition',
        and 'English Example' fields.

        Args:
            query (str): The search term.

        Returns:
            List[Dict[str, str]]: A list of matching vocabulary entries.
                                  Returns all entries if the query is empty.
        """
        try:
            vocabulary = self.get_all_vocabulary()
            if not query or not query.strip(): # If query is empty or just whitespace, return all
                return vocabulary
                
            query_lower = query.lower().strip()
            
            filtered_results = []
            for entry in vocabulary:
                # Check against None or missing keys before lowercasing
                english_word = entry.get('English Word', '')
                english_def = entry.get('English Definition', '')
                english_ex = entry.get('English Example', '')

                if (query_lower in english_word.lower() or 
                    query_lower in english_def.lower() or 
                    query_lower in english_ex.lower()):
                    filtered_results.append(entry)
            
            logging.info(f"Search for '{query}' found {len(filtered_results)} results.")
            return filtered_results
            
        except Exception as e:
            logging.error(f"Error searching vocabulary for query '{query}': {e}")
            return [] # Return empty list on error
    
    def delete_word(self, word: str) -> bool:
        """Deletes a word (case-insensitive) from the vocabulary CSV file.

        Args:
            word (str): The English word to delete.

        Returns:
            bool: True if the word was found and deleted, False otherwise.
        """
        if not word:
            logging.warning("delete_word called with an empty word.")
            return False
            
        word_to_delete_lower = word.lower().strip()
        try:
            vocabulary = self.get_all_vocabulary()
            if not vocabulary: # No words to delete from
                return False

            # Filter out the word to delete, comparing case-insensitively
            updated_vocabulary = [
                entry for entry in vocabulary 
                if entry.get('English Word', '').lower() != word_to_delete_lower
            ]
            
            if len(updated_vocabulary) == len(vocabulary):
                # Word not found, so no changes made
                logging.warning(f"Word '{word}' not found for deletion.")
                return False
            
            # Rewrite the CSV file with the updated vocabulary
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                # Ensure fieldnames are correctly sourced from self.headers
                writer = csv.DictWriter(file, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(updated_vocabulary)
            
            logging.info(f"Successfully deleted word: '{word}' from {self.csv_file}")
            return True
            
        except IOError as e:
            logging.error(f"IOError deleting word '{word}' from CSV {self.csv_file}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error deleting word '{word}': {e}")
            return False
    
    def get_word(self, word: str) -> Optional[Dict[str, str]]:
        """Get a specific word's data from the vocabulary.

        Args:
            word (str): The English word to look up.

        Returns:
            Optional[Dict[str, str]]: The word's data if found, None otherwise.
        """
        try:
            vocabulary = self.get_all_vocabulary()
            word_lower = word.lower().strip()
            for entry in vocabulary:
                if entry.get('English Word', '').lower() == word_lower:
                    return entry
            return None
        except Exception as e:
            logging.error(f"Error getting word '{word}': {e}")
            return None

    def update_word(self, word: str, new_data: Dict[str, str]) -> bool:
        """Update a word's data in the vocabulary.

        Args:
            word (str): The English word to update.
            new_data (Dict[str, str]): The new data for the word.

        Returns:
            bool: True if the word was updated successfully, False otherwise.
        """
        try:
            vocabulary = self.get_all_vocabulary()
            word_lower = word.lower().strip()
            updated = False
            
            for entry in vocabulary:
                if entry.get('English Word', '').lower() == word_lower:
                    entry.update(new_data)
                    updated = True
                    break
            
            if updated:
                with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=self.headers)
                    writer.writeheader()
                    writer.writerows(vocabulary)
                return True
            return False
        except Exception as e:
            logging.error(f"Error updating word '{word}': {e}")
            return False
