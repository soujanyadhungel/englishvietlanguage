import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from vocabulary_service import VocabularyService

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_vocabulary_secret_key")

# Initialize vocabulary service
vocab_service = VocabularyService()

@app.route('/')
def index():
    """Display the main vocabulary page with form and table."""
    try:
        vocabulary_data = vocab_service.get_all_vocabulary()
        return render_template('index.html', vocabulary_data=vocabulary_data)
    except Exception as e:
        logging.error(f"Error loading vocabulary data: {e}")
        flash(f"Error loading vocabulary data: {str(e)}", "error")
        return render_template('index.html', vocabulary_data=[])

@app.route('/add_word', methods=['POST'])
def add_word():
    """Add a new English word to the vocabulary."""
    english_word = request.form.get('english_word', '').strip()
    
    if not english_word:
        flash("Please enter an English word.", "error")
        return redirect(url_for('index'))
    
    if not english_word.replace(' ', '').isalpha():
        flash("Please enter a valid English word (letters only).", "error")
        return redirect(url_for('index'))
    
    try:
        # Check if word already exists
        if vocab_service.word_exists(english_word):
            flash(f"The word '{english_word}' already exists in your vocabulary.", "warning")
            return redirect(url_for('index'))
        
        # Add the word with automatic translations
        result = vocab_service.add_word(english_word)
        
        if result:
            flash(f"Successfully added '{english_word}' to your vocabulary!", "success")
        else:
            flash(f"Could not find definition for '{english_word}'. Please try another word.", "error")
            
    except Exception as e:
        logging.error(f"Error adding word '{english_word}': {e}")
        flash(f"An error occurred while adding the word: {str(e)}", "error")
    
    return redirect(url_for('index'))

@app.route('/search')
def search():
    """Search vocabulary entries."""
    query = request.args.get('q', '').strip().lower()
    
    if not query:
        return redirect(url_for('index'))
    
    try:
        vocabulary_data = vocab_service.search_vocabulary(query)
        flash(f"Found {len(vocabulary_data)} results for '{query}'", "info")
        return render_template('index.html', vocabulary_data=vocabulary_data, search_query=query)
    except Exception as e:
        logging.error(f"Error searching vocabulary: {e}")
        flash(f"Error searching vocabulary: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/export')
def export_csv():
    """Export vocabulary as CSV file."""
    try:
        csv_path = vocab_service.get_csv_path()
        return send_file(csv_path, as_attachment=True, download_name='vocabulary.csv')
    except Exception as e:
        logging.error(f"Error exporting CSV: {e}")
        flash(f"Error exporting CSV: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/delete_word/<word>')
def delete_word(word):
    """Delete a word from vocabulary."""
    try:
        if vocab_service.delete_word(word):
            flash(f"Successfully deleted '{word}' from your vocabulary.", "success")
        else:
            flash(f"Word '{word}' not found in vocabulary.", "error")
    except Exception as e:
        logging.error(f"Error deleting word '{word}': {e}")
        flash(f"Error deleting word: {str(e)}", "error")
    
    return redirect(url_for('index'))

@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    """Generate audio using Google Text-to-Speech API."""
    try:
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'en')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Generate audio using Google TTS
        audio_content = vocab_service.generate_audio(text, language)
        
        if audio_content:
            return jsonify({
                'success': True,
                'audio': audio_content,
                'message': 'Audio generated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to generate audio, using browser fallback'
            })
            
    except Exception as e:
        logging.error(f"Error generating audio: {e}")
        return jsonify({
            'success': False,
            'message': 'Audio generation failed, using browser fallback'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
