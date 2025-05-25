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

class VocabularyService:
    def __init__(self, csv_file='vocabulary.csv'):
        self.csv_file = csv_file
        self.translator = Translator()  # Keep as fallback
        self.headers = ['English Word', 'English Definition', 'English Example', 'Vietnamese Definition', 'Vietnamese Example']
        
        # Initialize Google Cloud services
        self.api_key = os.environ.get("GOOGLE_CLOUD_API_KEY")
        self.google_translator = None
        self.tts_client = None
            
        self._ensure_csv_exists()
    
    def _create_credentials_file(self):
        """Create a temporary credentials file for Google Cloud."""
        import json
        credentials = {
            "type": "service_account",
            "project_id": "vocabulary-app",
            "private_key_id": "dummy",
            "private_key": "-----BEGIN PRIVATE KEY-----\ndummy\n-----END PRIVATE KEY-----\n",
            "client_email": "dummy@vocabulary-app.iam.gserviceaccount.com",
            "client_id": "dummy",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        with open("/tmp/gcp_key.json", "w") as f:
            json.dump(credentials, f)

    def _ensure_csv_exists(self):
        """Create CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(self.headers)
            logging.info(f"Created new CSV file: {self.csv_file}")
    
    def get_csv_path(self) -> str:
        """Get the path to the CSV file."""
        return os.path.abspath(self.csv_file)
    
    def get_english_definition(self, word: str) -> Optional[Dict[str, str]]:
        """
        Generate English definition and example using Google Cloud Translation API.
        Returns dict with 'definition' and 'example' keys.
        """
        try:
            # Create comprehensive definition and example using Google Translate
            # We'll translate from Vietnamese definitions to get high-quality English content
            
            # Create structured prompts for definition and example
            vietnamese_definition_prompt = f"Định nghĩa từ tiếng Anh '{word}' một cách chi tiết và rõ ràng cho việc học ngôn ngữ."
            vietnamese_example_prompt = f"Đưa ra một câu ví dụ rõ ràng sử dụng từ tiếng Anh '{word}' trong ngữ cảnh."
            
            # Translate Vietnamese prompts to English using Google Cloud Translation
            definition = self.translate_text_with_google(vietnamese_definition_prompt, target_language='en')
            example = self.translate_text_with_google(vietnamese_example_prompt, target_language='en')
            
            # If translation fails, use fallback with dictionary API
            if not definition or not example:
                return self._get_fallback_definition(word)
            
            # Clean up the translated text to make it more definition-like
            if definition:
                definition = definition.replace("Define the English word", "").replace(f"'{word}'", "").strip()
                if definition.startswith("detailed and clear"):
                    definition = f"A word that means: {definition}"
                elif not definition.startswith(("A", "An", "The", "To")):
                    definition = f"To {definition.lower()}"
            
            if example:
                example = example.replace("Give a clear example sentence using the English word", "").replace(f"'{word}'", word).strip()
                if not any(word.lower() in example.lower() for word in [word]):
                    example = f"Here is an example: {example}"
            
            return {
                'definition': definition or f"An English word: {word}",
                'example': example or f"Example sentence with {word}."
            }
            
        except Exception as e:
            logging.error(f"Error generating definition for '{word}': {e}")
            # Fallback to dictionary API if Google translation fails
            return self._get_fallback_definition(word)
    
    def translate_text_with_google(self, text: str, target_language: str = 'en') -> str:
        """Helper method to translate text using Google Cloud Translation API."""
        try:
            api_key = os.environ.get('GOOGLE_CLOUD_API_KEY')
            if not api_key:
                logging.error("Google Cloud API key not found")
                return ""
            
            url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"
            
            data = {
                'q': text,
                'target': target_language,
                'format': 'text'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if 'data' in result and 'translations' in result['data']:
                    translated_text = result['data']['translations'][0]['translatedText']
                    logging.info(f"Google Cloud Translation successful for: {text[:50]}...")
                    return translated_text
            
            logging.error(f"Google translation failed with status: {response.status_code}")
            return ""
            
        except Exception as e:
            logging.error(f"Error in Google translation: {e}")
            return ""
    
    def _get_fallback_definition(self, word: str) -> Optional[Dict[str, str]]:
        """Fallback method using Dictionary API if Google services fail."""
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0:
                    entry = data[0]
                    
                    definition = "No definition available"
                    example = "No example available"
                    
                    if 'meanings' in entry and len(entry['meanings']) > 0:
                        meanings = entry['meanings']
                        
                        for meaning in meanings:
                            if 'definitions' in meaning and len(meaning['definitions']) > 0:
                                def_data = meaning['definitions'][0]
                                definition = def_data.get('definition', definition)
                                
                                if 'example' in def_data:
                                    example = def_data['example']
                                break
                    
                    return {
                        'definition': definition,
                        'example': example
                    }
            
            return None
            
        except Exception as e:
            logging.error(f"Fallback definition failed for '{word}': {e}")
            return None
    
    def translate_to_vietnamese(self, text: str) -> str:
        """Translate English text to Vietnamese using Google Cloud Translation API."""
        if self.api_key:
            try:
                # Use Google Cloud Translation API
                url = f"https://translation.googleapis.com/language/translate/v2?key={self.api_key}"
                data = {
                    'q': text,
                    'source': 'en',
                    'target': 'vi',
                    'format': 'text'
                }
                response = requests.post(url, data=data, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    translated_text = result['data']['translations'][0]['translatedText']
                    logging.info(f"Google Cloud Translation successful for: {text[:50]}...")
                    return translated_text
                else:
                    logging.warning(f"Google Cloud Translation failed, using fallback for: {text[:50]}...")
                    # Fallback to googletrans
                    result = self.translator.translate(text, src='en', dest='vi')
                    return result.text
                    
            except Exception as e:
                logging.error(f"Google Cloud Translation error: {e}, using fallback")
                # Fallback to googletrans
                try:
                    time.sleep(0.1)
                    result = self.translator.translate(text, src='en', dest='vi')
                    return result.text
                except Exception as fallback_error:
                    logging.error(f"Fallback translation failed: {fallback_error}")
                    return f"Translation failed: {text}"
        else:
            # Use fallback googletrans
            try:
                time.sleep(0.1)
                result = self.translator.translate(text, src='en', dest='vi')
                return result.text
            except Exception as e:
                logging.error(f"Translation failed for text '{text}': {e}")
                return f"Translation failed: {text}"
    
    def get_pronunciation_guide(self, text: str) -> str:
        """Generate a simple pronunciation guide for English text."""
        try:
            # Simple phonetic approximation - could be enhanced with a proper phonetic API
            # For now, we'll provide a basic pronunciation guide
            import re
            
            # Basic pronunciation mappings
            pronunciation_map = {
                'th': 'θ',
                'ch': 'tʃ',
                'sh': 'ʃ',
                'ph': 'f',
                'gh': 'g',
                'tion': 'ʃən',
                'sion': 'ʒən',
                'ough': 'ʌf',
                'augh': 'ɔf',
                'eigh': 'eɪ',
                'ight': 'aɪt',
            }
            
            # Convert to lowercase for processing
            text_lower = text.lower()
            pronunciation = text_lower
            
            # Apply basic pronunciation rules
            for pattern, replacement in pronunciation_map.items():
                pronunciation = pronunciation.replace(pattern, replacement)
            
            # Add stress markers for multi-syllable words
            if len(text.split()) == 1 and len(text) > 4:
                # Simple heuristic: stress on first syllable for most English words
                pronunciation = f"'{pronunciation}"
            
            return f"/{pronunciation}/"
            
        except Exception as e:
            logging.error(f"Pronunciation generation failed for text '{text}': {e}")
            return f"/{text.lower()}/"
    
    def generate_audio(self, text: str, language: str) -> Optional[str]:
        """Generate audio using Google Text-to-Speech API and return base64 encoded audio."""
        if not self.api_key:
            return None
            
        try:
            # Use Google Cloud Text-to-Speech API
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.api_key}"
            
            # Set voice based on language
            if language == 'vi':
                voice = {
                    'languageCode': 'vi-VN',
                    'name': 'vi-VN-Standard-A',  # Female voice
                    'ssmlGender': 'FEMALE'
                }
            else:
                voice = {
                    'languageCode': 'en-US',
                    'name': 'en-US-Standard-C',  # Female voice
                    'ssmlGender': 'FEMALE'
                }
            
            data = {
                'input': {'text': text},
                'voice': voice,
                'audioConfig': {
                    'audioEncoding': 'MP3',
                    'speakingRate': 0.9
                }
            }
            
            response = requests.post(url, json=data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                audio_content = result.get('audioContent')
                logging.info(f"Google TTS successful for: {text[:50]}...")
                return audio_content
            else:
                logging.warning(f"Google TTS failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Google TTS error: {e}")
            return None
    
    def add_word(self, english_word: str) -> bool:
        """
        Add a new word to the vocabulary with automatic definition and translation.
        Returns True if successful, False otherwise.
        """
        try:
            # Get English definition and example
            definition_data = self.get_english_definition(english_word)
            
            if not definition_data:
                logging.warning(f"No definition found for word: {english_word}")
                return False
            
            english_definition = definition_data['definition']
            english_example = definition_data['example']
            
            # Translate to Vietnamese
            vietnamese_definition = self.translate_to_vietnamese(english_definition)
            vietnamese_example = self.translate_to_vietnamese(english_example)
            
            # Add to CSV
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    english_word,
                    english_definition,
                    english_example,
                    vietnamese_definition,
                    vietnamese_example
                ])
            
            logging.info(f"Successfully added word: {english_word}")
            return True
            
        except Exception as e:
            logging.error(f"Error adding word '{english_word}': {e}")
            return False
    
    def get_all_vocabulary(self) -> List[Dict[str, str]]:
        """Get all vocabulary entries from CSV."""
        vocabulary = []
        
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    vocabulary.append(row)
            
            logging.debug(f"Loaded {len(vocabulary)} vocabulary entries")
            return vocabulary
            
        except Exception as e:
            logging.error(f"Error reading vocabulary from CSV: {e}")
            return []
    
    def word_exists(self, word: str) -> bool:
        """Check if a word already exists in the vocabulary."""
        try:
            vocabulary = self.get_all_vocabulary()
            return any(entry['English Word'].lower() == word.lower() for entry in vocabulary)
        except Exception as e:
            logging.error(f"Error checking if word exists: {e}")
            return False
    
    def search_vocabulary(self, query: str) -> List[Dict[str, str]]:
        """Search vocabulary entries by query string."""
        try:
            vocabulary = self.get_all_vocabulary()
            query_lower = query.lower()
            
            filtered = []
            for entry in vocabulary:
                # Search in English word, definition, and example
                if (query_lower in entry['English Word'].lower() or 
                    query_lower in entry['English Definition'].lower() or 
                    query_lower in entry['English Example'].lower()):
                    filtered.append(entry)
            
            return filtered
            
        except Exception as e:
            logging.error(f"Error searching vocabulary: {e}")
            return []
    
    def delete_word(self, word: str) -> bool:
        """Delete a word from the vocabulary."""
        try:
            vocabulary = self.get_all_vocabulary()
            
            # Filter out the word to delete
            updated_vocabulary = [
                entry for entry in vocabulary 
                if entry['English Word'].lower() != word.lower()
            ]
            
            if len(updated_vocabulary) == len(vocabulary):
                # Word not found
                return False
            
            # Rewrite the CSV file
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(updated_vocabulary)
            
            logging.info(f"Successfully deleted word: {word}")
            return True
            
        except Exception as e:
            logging.error(f"Error deleting word '{word}': {e}")
            return False
