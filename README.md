# English-Vietnamese Vocabulary Learning App

## 📚 What It Does
A smart vocabulary learning application designed to help users build their English and Vietnamese vocabulary. Enter an English word, and the app automatically fetches its English definition and an example sentence. It then translates both the definition and example into Vietnamese. The application also provides text-to-speech functionality for both English and Vietnamese words and phrases, utilizing Google Cloud services when available.

## 🏗️ Technical Architecture

### **Backend Stack**
- **Language**: Python (designed for 3.11+)
- **Framework**: Flask (for the web application interface)
- **Data Storage**: CSV file (`vocabulary.csv`) for easy portability and management of vocabulary lists.
- **Server**: Gunicorn (recommended for production)

### **Frontend Stack**
- **Structure**: HTML (`index.html`)
- **Styling**: CSS (`style.css`), Bootstrap 5 (responsive, dark theme)
- **Interactivity**: Vanilla JavaScript
- **Icons**: Font Awesome

### **Core Services & APIs**
The application leverages external APIs for definitions, translations, and text-to-speech:

1.  **English Definitions & Examples**:
    *   **Primary**: Attempts to generate contextually relevant definitions and examples by translating Vietnamese prompts using **Google Cloud Translation API** (requires `GOOGLE_CLOUD_API_KEY`).
    *   **Fallback**: If the primary method fails or an API key is not provided, it uses the [Free Dictionary API](https://dictionaryapi.dev/) (no key required).

2.  **Translation (English to Vietnamese)**:
    *   **Primary**: Uses **Google Cloud Translation API** (requires `GOOGLE_CLOUD_API_KEY`) for high-quality translations of definitions and examples.
    *   **Fallback**: If the primary method fails or an API key is not provided, it uses the `googletrans` library.

3.  **Text-to-Speech (English & Vietnamese)**:
    *   **Primary**: Uses **Google Cloud Text-to-Speech API** (requires `GOOGLE_CLOUD_API_KEY`) for natural-sounding audio.
    *   **Fallback**: If the API key is not provided or the API call fails, the frontend may attempt to use the browser's built-in Web Speech API for English (though this is a client-side fallback and not directly controlled by the backend's `generate_audio` endpoint if the Google Cloud TTS fails).

## 🔧 How It Works

1.  **User Input**: The user enters an English word into the web interface.
2.  **Definition & Example Generation**:
    *   The backend `VocabularyService` first tries to generate an English definition and example using a creative prompting strategy with the Google Cloud Translation API (if `GOOGLE_CLOUD_API_KEY` is set).
    *   If this fails, it falls back to the Free Dictionary API.
3.  **Translation**: The obtained English definition and example are translated into Vietnamese, prioritizing Google Cloud Translation API and falling back to `googletrans`.
4.  **Storage**: The English word, its English definition/example, and the Vietnamese translations are saved into the `vocabulary.csv` file.
5.  **Display**: The vocabulary list is displayed in a table on the web page.
6.  **Audio Playback**: Users can click icons to hear the pronunciation. This triggers a call to the backend `/generate_audio` endpoint, which uses Google Cloud Text-to-Speech API (if `GOOGLE_CLOUD_API_KEY` is set) to generate and send back the audio. If the backend service fails to generate audio, the frontend has a browser-based speech synthesis as a last resort for English text.

## ✨ Key Features
- Automatic English definition and example sentence generation for entered words.
- Automatic Vietnamese translation of English definitions and examples.
- Text-to-Speech for English words/phrases and Vietnamese translations (powered by Google Cloud TTS when API key is available).
- Vocabulary data stored in a simple CSV file (`vocabulary.csv`).
- Export vocabulary to CSV.
- Search functionality for the vocabulary list.
- Ability to delete words from the vocabulary.
- Responsive, dark-themed web interface.

## 🛠️ Setup and Running the Application

### **Prerequisites**
- Python 3.11 or newer.
- `pip3` (Python package installer).
- (Optional but Recommended) A **Google Cloud API Key** with "Cloud Translation API" and "Cloud Text-to-Speech API" enabled.

### **Installation**
1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Set up Google Cloud API Key (Recommended):**
    Export your API key as an environment variable. Replace `"YOUR_API_KEY"` with your actual key.
    ```bash
    export GOOGLE_CLOUD_API_KEY=\"YOUR_API_KEY\"
    ```
    You can add this line to your shell's configuration file (e.g., `~/.bashrc`, `~/.zshrc`) to make it permanent.

3.  **Install Dependencies:**
    The project uses dependencies listed in `pyproject.toml`. Install them using `pip3`:
    ```bash
    pip3 install email-validator flask flask-sqlalchemy google-cloud-texttospeech google-cloud-translate googletrans==4.0.0rc1 gunicorn psycopg2-binary requests
    ```
    *(Note: `flask-sqlalchemy` and `psycopg2-binary` are listed but not actively used by the core CSV-based vocabulary features at the moment.)*

### **Running the Application**
1.  **Development Server (Flask built-in):**
    Good for testing and development.
    ```bash
    python3 main.py
    ```
    The application will typically be available at `http://0.0.0.0:5000` or `http://localhost:5000`.

2.  **Production Server (Gunicorn):**
    Recommended for a more robust deployment.
    ```bash
    gunicorn --bind 0.0.0.0:5000 main:app
    ```

## 🧪 Running Tests
Unit tests are provided for the `VocabularyService`. To run them:
```bash
python3 -m unittest test_vocabulary_service.py
```
Ensure your `GOOGLE_CLOUD_API_KEY` is set in the environment, although the tests mock its usage for API calls.

## 📂 Project Structure
```
.
├── app.py                  # Flask application routes and logic
├── main.py                 # Main entry point to run the Flask app
├── vocabulary_service.py   # Core logic for vocabulary, definitions, translations, TTS
├── vocabulary.csv          # Stores the vocabulary data
├── templates/
│   └── index.html          # Main HTML page for the UI
├── static/
│   └── style.css           # CSS styles for the application
│   └── (other static assets like images if any)
├── test_vocabulary_service.py # Unit tests for VocabularyService
├── pyproject.toml          # Project metadata and dependencies (for uv/pip)
├── README.md               # This file
└── .git/                   # Git version control data
```

## 🚀 Potential Future Enhancements
- **Improved UI/UX**: More interactive elements, loading indicators for API calls.
- **Error Handling**: More granular error messages on the frontend.
- **Duplicate Word Check in Service**: Add `word_exists` check within `VocabularyService.add_word` to prevent duplicates at the service layer.
- **Configuration File**: For API keys and other settings instead of only environment variables.
- **Database Integration**: Switch from CSV to a database like SQLite or PostgreSQL for larger datasets and more complex queries (dependencies like `flask-sqlalchemy` and `psycopg2-binary` are already in `pyproject.toml`).
- **User Accounts**: To allow users to have their own separate vocabulary lists.

---

*This application demonstrates building a useful language learning tool by integrating Python, Flask, and various web APIs, including powerful Google Cloud services.*