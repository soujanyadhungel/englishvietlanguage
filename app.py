import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from vocabulary_service import VocabularyService

# Configure logging to output to stdout/stderr for Vercel
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Only use StreamHandler for Vercel
    ]
)

app = Flask(__name__)
# Secret key for session management (e.g., for flash messages).
# It's good practice to set this from an environment variable in production.
app.secret_key = os.environ.get("SESSION_SECRET", "default_vocabulary_secret_key")

# Initialize vocabulary service, which handles all business logic related to vocabulary.
vocab_service = VocabularyService()

@app.route('/')
def index():
    """Display the main vocabulary page.
    
    Renders the `index.html` template, passing in the current vocabulary data.
    Handles potential errors during data loading and flashes an error message.
    """
    try:
        vocabulary_data = vocab_service.get_all_vocabulary()
        return render_template('index.html', vocabulary_data=vocabulary_data)
    except Exception as e:
        logging.error(f"Error loading vocabulary data: {e}")
        flash(f"Error loading vocabulary data: {str(e)}", "error")
        return render_template('index.html', vocabulary_data=[]) # Return empty list on error

@app.route('/add_word', methods=['POST'])
def add_word():
    """Handle the addition of a new English word to the vocabulary."""
    english_word = request.form.get('english_word', '').strip()
    
    if not english_word:
        flash('Please enter an English word.', 'error')
        return redirect(url_for('index'))
    
    if not all(char.isalpha() or char.isspace() for char in english_word):
        flash('Please enter a valid English word (letters and spaces only).', 'error')
        return redirect(url_for('index'))
    
    try:
        if vocab_service.word_exists(english_word):
            flash(f"The word '{english_word}' already exists in your vocabulary.", 'warning')
            return redirect(url_for('index'))
        
        result = vocab_service.add_word(english_word)
        
        if result:
            flash(f"Successfully added '{english_word}' to your vocabulary.", 'success')
        else:
            flash('Could not find definition or translate the word. Word not added.', 'error')
            
    except Exception as e:
        logging.error(f"Error adding word '{english_word}': {e}")
        flash(f"An unexpected error occurred: {str(e)}", 'error')
    
    return redirect(url_for('index'))

@app.route('/search')
def search():
    """Handle searching for words within the vocabulary.
    
    Retrieves the search query from the request arguments.
    Uses `VocabularyService` to perform the search.
    Flashes the number of results found.
    Renders the `index.html` template with the filtered vocabulary data.
    """
    query = request.args.get('q', '').strip().lower()
    
    if not query:
        # If search query is empty, redirect to the main page (display all words)
        return redirect(url_for('index'))
    
    try:
        vocabulary_data = vocab_service.search_vocabulary(query)
        flash(f"Found {len(vocabulary_data)} results for '{query}'", "info")
        return render_template('index.html', vocabulary_data=vocabulary_data, search_query=query)
    except Exception as e:
        logging.error(f"Error searching vocabulary: {e}")
        flash(f"Error searching vocabulary: {str(e)}", "error")
        # On error, redirect to index, showing all vocabulary might be better than showing none
        return redirect(url_for('index'))

@app.route('/export')
def export_csv():
    """Handle the export of the vocabulary list as a CSV file.
    
    Uses `VocabularyService` to get the path to the CSV file.
    Sends the file to the user for download.
    Handles potential errors during export.
    """
    try:
        csv_path = vocab_service.get_csv_path()
        return send_file(csv_path, as_attachment=True, download_name='vocabulary.csv')
    except Exception as e:
        logging.error(f"Error exporting CSV: {e}")
        flash(f"Error exporting CSV: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/delete_word/<word>')
def delete_word(word):
    """Handle the deletion of a specific word from the vocabulary.
    
    The word to be deleted is passed as a URL parameter.
    Uses `VocabularyService` to delete the word.
    Flashes success or error messages.
    Redirects back to the index page.
    """
    try:
        if vocab_service.delete_word(word):
            flash(f"Successfully deleted '{word}' from your vocabulary.", "success")
        else:
            # This might happen if the word was already deleted or never existed.
            flash(f"Word '{word}' not found in vocabulary or could not be deleted.", "error")
    except Exception as e:
        logging.error(f"Error deleting word '{word}': {e}")
        flash(f"Error deleting word: {str(e)}", "error")
    
    return redirect(url_for('index'))

@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    """Generate audio for a given text string using the selected TTS service (Google, ElevenLabs, or browser)."""
    try:
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'en') # Default to English if language not specified
        service = data.get('service', 'google') # New: which TTS service to use
        if not text:
            return jsonify({'error': 'No text provided for audio generation'}), 400
        # Generate audio using the vocabulary service
        audio_content = vocab_service.generate_audio(text, language, service)
        if audio_content:
            return jsonify({
                'success': True,
                'audio': audio_content,
                'message': f'Audio generated successfully via {service.title()} TTS.'
            })
        else:
            logging.warning(f"Audio generation failed for text: '{text[:50]}...'. Backend TTS might be unavailable.")
            return jsonify({
                'success': False,
                'message': f'Backend audio generation failed for {service.title()}. Browser fallback may be used if available.'
            })
    except Exception as e:
        logging.error(f"Error in /generate_audio endpoint: {e}")
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred during audio generation. Browser fallback may be used if available.'
        }), 500

@app.route('/refresh_cell', methods=['POST'])
def refresh_cell():
    """Refresh a cell (definition/example/vn_definition) for a word using Google Translate API."""
    try:
        data = request.get_json()
        word = data.get('word', '').strip()
        column = data.get('column', '').strip()  # 'definition', 'example', 'vn_definition'
        if not word or column not in ['definition', 'example', 'vn_definition']:
            return jsonify({'success': False, 'message': 'Invalid request.'}), 400
        # Get a new definition/example from Google Translate API
        def_data = vocab_service.get_english_definition(word)
        if not def_data:
            return jsonify({'success': False, 'message': 'Could not fetch new data.'}), 500
        if column == 'definition':
            new_value = def_data.get('definition', '')
        elif column == 'example':
            new_value = def_data.get('example', '')
        elif column == 'vn_definition':
            # Get new English definition, then translate to Vietnamese
            en_def = def_data.get('definition', '')
            new_value = vocab_service.translate_to_vietnamese(en_def)
        else:
            new_value = ''
        return jsonify({'success': True, 'new_value': new_value})
    except Exception as e:
        logging.error(f"Error in /refresh_cell endpoint: {e}")
        return jsonify({'success': False, 'message': 'An error occurred.'}), 500

@app.route('/refresh_content', methods=['POST'])
def refresh_content():
    """Refresh content for a specific word and column."""
    try:
        data = request.get_json()
        word = data.get('word')
        column = data.get('column')
        
        logging.info(f"Refresh request received for word '{word}' and column '{column}'")
        
        if not word or not column:
            logging.error("Missing word or column parameter in refresh request")
            return jsonify({'success': False, 'message': 'Missing word or column parameter'}), 400
            
        # Get the word's current data
        word_data = vocab_service.get_word(word)
        if not word_data:
            logging.error(f"Word '{word}' not found in vocabulary")
            return jsonify({'success': False, 'message': 'Word not found'}), 404
            
        logging.info(f"Current data for word '{word}': {word_data}")
        
        # Generate new content based on the column
        new_content = None
        if column == 'definition':
            logging.info(f"Refreshing English definition for '{word}'")
            def_data = vocab_service.get_english_definition(word)
            if def_data and def_data.get('definition'):
                new_content = def_data['definition']
                word_data['English Definition'] = new_content
                logging.info(f"New English definition: {new_content}")
        elif column == 'example':
            logging.info(f"Refreshing English example for '{word}'")
            def_data = vocab_service.get_english_definition(word)
            if def_data and def_data.get('example'):
                new_content = def_data['example']
                word_data['English Example'] = new_content
                logging.info(f"New English example: {new_content}")
        elif column == 'vietnamese_definition':
            logging.info(f"Refreshing Vietnamese definition for '{word}'")
            new_content = vocab_service.translate_to_vietnamese(word_data['English Definition'])
            if new_content:
                word_data['Vietnamese Definition'] = new_content
                logging.info(f"New Vietnamese definition: {new_content}")
        elif column == 'vietnamese_example':
            logging.info(f"Refreshing Vietnamese example for '{word}'")
            new_content = vocab_service.translate_to_vietnamese(word_data['English Example'])
            if new_content:
                word_data['Vietnamese Example'] = new_content
                logging.info(f"New Vietnamese example: {new_content}")
                
        if not new_content:
            logging.error(f"Failed to generate new content for word '{word}' and column '{column}'")
            return jsonify({'success': False, 'message': 'Failed to generate new content'}), 500
            
        # Update the word in the vocabulary
        if vocab_service.update_word(word, word_data):
            logging.info(f"Successfully updated word '{word}' with new content")
            return jsonify({'success': True, 'content': new_content})
        else:
            logging.error(f"Failed to update word '{word}' in vocabulary")
            return jsonify({'success': False, 'message': 'Failed to update word in vocabulary'}), 500
            
    except Exception as e:
        logging.error(f"Error in /refresh_content endpoint: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# This check ensures that app.run() is only called when main.py is executed directly,
# and not, for example, when imported by another script or when run by a WSGI server like Gunicorn.
if __name__ == '__main__':
    # Runs the Flask development server.
    # host='0.0.0.0' makes the server accessible from any network interface (not just localhost).
    # debug=True enables Flask's debugger and auto-reloader, useful for development.
    # In production, a proper WSGI server like Gunicorn should be used (see README).
    app.run(host='0.0.0.0', port=5001, debug=True)
