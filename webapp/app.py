from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
import subprocess
import whisper
import logging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['DOWNLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'wav', 'mp3'}
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

logging.basicConfig(level=logging.INFO)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext == 'mp4':
            process_video(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            process_audio(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        srt_file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], filename.rsplit('.', 1)[0] + '.srt')
        with open(srt_file_path, "r", encoding='utf-8') as file:
            srt_content = file.read()

        # Delete the uploaded and created files
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        os.remove(srt_file_path)

        return jsonify({"srt_content": srt_content})
    return jsonify({"error": "Invalid file type"}), 400

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename)

def process_video(video_path):
    video_output_path = 'output_video.mp4'
    audio_output_path = 'audio.wav'

    extract_video_and_audio(video_path, video_output_path, audio_output_path)
    os.remove(video_output_path)
    segments = transcribe_audio("small", audio_output_path)
    convert_to_srt(segments, os.path.join(app.config['DOWNLOAD_FOLDER'], video_path.rsplit(os.sep, 1)[1].rsplit('.', 1)[0] + '.srt'))
    os.remove(audio_output_path)

def process_audio(audio_path):
    audio_output_path = 'audio.wav'
    if audio_path.rsplit('.', 1)[1].lower() != 'wav':
        subprocess.call(['ffmpeg', '-y', '-i', audio_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', audio_output_path])
        os.remove(audio_path)
    else:
        audio_output_path = audio_path
    segments = transcribe_audio("small", audio_output_path)
    convert_to_srt(segments, os.path.join(app.config['DOWNLOAD_FOLDER'], audio_path.rsplit(os.sep, 1)[1].rsplit('.', 1)[0] + '.srt'))
    os.remove(audio_output_path)

def extract_video_and_audio(video_path, video_output_path, audio_output_path):
    subprocess.call(['ffmpeg', '-y', '-i', video_path, '-c:v', 'copy', '-an', video_output_path])
    subprocess.call(['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', audio_output_path])

def transcribe_audio(model_name, audio_output_path):
    model = whisper.load_model(model_name)
    logging.info("Model loaded")
    result = model.transcribe(audio_output_path)
    return result["segments"]

def convert_to_srt(output, srt_filename):
    srt_content = ""
    for index, item in enumerate(output):
        start_time = item['start']
        end_time = item['end']
        text = item['text']

        start_time_srt = format(int(start_time // 3600), "02") + ":" + format(int((start_time % 3600) // 60), "02") + ":" + format(start_time % 60, "06.3f").replace(".", ",")
        end_time_srt = format(int(end_time // 3600), "02") + ":" + format(int((end_time % 3600) // 60), "02") + ":" + format(end_time % 60, "06.3f").replace(".", ",")

        entry = f"{index + 1}\n{start_time_srt} --> {end_time_srt}\n{text}\n\n"
        srt_content += entry

    srt_file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], srt_filename)
    with open(srt_file_path, "w", encoding='utf-8') as file:
        file.write(srt_content)

if __name__ == '__main__':
    app.run(debug=True)
