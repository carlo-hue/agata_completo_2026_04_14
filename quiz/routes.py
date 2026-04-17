from flask import render_template, request, current_app, send_from_directory
from agata.auth.decorators import login_required
from . import quiz_bp
import os
import json
import uuid
import qrcode
from PIL import Image, ImageDraw, ImageFont

# Carica le domande
questions_file_path = os.path.join(os.path.dirname(__file__), 'questions.json')
with open(questions_file_path) as f:
    QUESTIONS = json.load(f)

@quiz_bp.route('/')
@login_required
def index():
    return render_template('quiz/index.html')

@quiz_bp.route('/quiz', methods=['GET', 'POST'])
@login_required
def quiz():
    if request.method == 'POST':
        answers = request.form
        user_name = answers.get('user_name', 'Partecipante').strip()
        correct = 0
        for i, q in enumerate(QUESTIONS):
            if answers.get(f'q{i}') == q['answer']:
                correct += 1

        if correct == len(QUESTIONS):
            # Genera diploma e QR
            diploma_id = str(uuid.uuid4())
            filename = f"{diploma_id}.png"
            upload_path = current_app.config['QUIZ_UPLOAD_FOLDER']
            os.makedirs(upload_path, exist_ok=True)

            # Dati fittizi per esempio
            user_name = "Partecipante"  # Puoi sostituirlo con current_user.name se usi flask-login

            # Genera diploma
            diploma_path = os.path.join(upload_path, filename)
            create_diploma(diploma_path, user_name, diploma_id)

            return render_template('success.html', qr_file=filename)
        else:
            return render_template('fail.html', correct=correct, total=len(QUESTIONS))

    return render_template('quiz.html', questions=QUESTIONS, enumerate=enumerate)

@quiz_bp.route('/diploma/<filename>')
@login_required
def serve_diploma(filename):
    return send_from_directory(current_app.config["QUIZ_UPLOAD_FOLDER"], filename)


def create_diploma(path, user_name, diploma_id):
    # Carica template diploma
    base = Image.open("static/template_diploma.png").convert("RGB")
    draw = ImageDraw.Draw(base)

    # Font
    font_path = "static/fonts/arial.ttf"
    font = ImageFont.truetype(font_path, 40)

    # Scrivi il nome sul diploma
    draw.text((300, 300), f"Congratulazioni {user_name}!", fill="black", font=font)
    draw.text((300, 360), "Hai completato con successo il quiz di AstroGen", fill="black", font=font)

    # Genera QR code personalizzato
    qr_link = f"https://app.astrogen.it/quiz/diploma/{diploma_id}.png"
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(qr_link)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Logo al centro
    logo = Image.open("static/logo.png").resize((60, 60))
    pos = ((qr_img.size[0] - logo.size[0]) // 2, (qr_img.size[1] - logo.size[1]) // 2)
    qr_img.paste(logo, pos, mask=logo)

    # Inserisci QR sul diploma
    base.paste(qr_img, (50, base.height - 250))

    # Salva diploma
    base.save(path)
