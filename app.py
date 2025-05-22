import os
import json
import random
import string
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from datetime import datetime
from fpdf import FPDF

# Chemin absolu pour Railway/Linux
BASEDIR = os.path.abspath(os.path.dirname(__file__))
RESERVATION_FILE = os.path.join(BASEDIR, 'reservations.json')
ADMIN_CODE = 's0r1'

EMOJIS = ['😸','🐶','🐰','🦊','🐻','🐼','🐨','🐯','🦁','🐷','🐸','🐵','🐔','🐧','🐦','🐤','🐢','🐍','🦄','🐝','🦋','🐞','🐙','🦑','🦞','🐳','🐬','🦈','🦭','🐊']

app = Flask(__name__)

def load_reservations():
    if not os.path.exists(RESERVATION_FILE):
        with open(RESERVATION_FILE, 'w') as f:
            json.dump([], f)
    with open(RESERVATION_FILE, 'r') as f:
        return json.load(f)

def save_reservations(reservations):
    with open(RESERVATION_FILE, 'w') as f:
        json.dump(reservations, f, indent=2)

def generate_code():
    return ''.join(random.choices(string.digits, k=4))

def generate_emoji():
    return random.choice(EMOJIS)

def can_reserve(chambre, date, machine, reservations):
    count = sum(1 for r in reservations if r['chambre'] == chambre and r['date'] == date and r['machine'] == machine)
    return count < 3

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calendar')
def calendar():
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory(BASEDIR, 'manifest.json', mimetype='application/json')

@app.route('/service-worker.js')
def sw():
    response = make_response(send_from_directory(BASEDIR, 'service-worker.js'))
    response.headers['Content-Type'] = 'application/javascript'
    return response

@app.route('/reservations', methods=['GET'])
def get_reservations():
    reservations = load_reservations()
    return jsonify(reservations)

@app.route('/reservation', methods=['POST'])
def add_reservation():
    data = request.get_json()
    chambre = data['chambre']
    date = data['date']
    heure = data['heure']
    machine = data['machine']
    code = generate_code()
    emoji = generate_emoji()

    # Validation horaire (7h à 23h)
    h = int(heure.split(':')[0])
    if h < 7 or h > 22:
        return jsonify({'success': False, 'msg': "Horaires autorisés : 7h à 23h."}), 400

    # Refus si passé
    res_date_time = datetime.strptime(f"{date} {heure}", "%Y-%m-%d %H:%M")
    if res_date_time < datetime.now():
        return jsonify({'success': False, 'msg': "Impossible de réserver dans le passé."}), 400

    reservations = load_reservations()

    # Refus si créneau déjà réservé
    for r in reservations:
        if r['date'] == date and r['heure'] == heure and r['machine'] == machine:
            return jsonify({'success': False, 'msg': "Créneau déjà réservé."}), 400

    # Limite 3 tournées/jour/machine/chambre
    if not can_reserve(chambre, date, machine, reservations):
        return jsonify({'success': False, 'msg': "Limite de 3 tournées par jour et par machine atteinte."}), 400

    reservation = {
        'chambre': chambre,
        'date': date,
        'heure': heure,
        'machine': machine,
        'code': code,
        'emoji': emoji
    }
    reservations.append(reservation)
    save_reservations(reservations)
    return jsonify({'success': True, 'code': code, 'emoji': emoji})

@app.route('/reservation', methods=['DELETE'])
def delete_reservation():
    data = request.get_json()
    chambre = data['chambre']
    date = data['date']
    heure = data['heure']
    machine = data['machine']
    code = data['code']

    reservations = load_reservations()
    found = False
    new_reservations = []
    for r in reservations:
        if r['chambre'] == chambre and r['date'] == date and r['heure'] == heure and r['machine'] == machine:
            if r['code'] == code or code == ADMIN_CODE:
                found = True
                continue
        new_reservations.append(r)
    if found:
        save_reservations(new_reservations)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'msg': "❌ Code incorrect"}), 400

@app.route('/ticket', methods=['POST'])
def ticket():
    data = request.get_json()
    chambre = data['chambre']
    date = data['date']
    heure = data['heure']
    machine = data['machine']
    code = data['code']
    emoji = data['emoji']

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, "Ticket de Réservation Buanderie", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(0, 10, f"Chambre : {chambre}", ln=True)
    pdf.cell(0, 10, f"Date : {date}", ln=True)
    pdf.cell(0, 10, f"Heure : {heure}", ln=True)
    pdf.cell(0, 10, f"Machine : {machine}", ln=True)
    pdf.cell(0, 10, f"Code de suppression : {code} {emoji}", ln=True)
    pdf.ln(10)
    pdf.cell(0, 10, "Merci d'utiliser le service !", ln=True)
    pdf_file = f"ticket_{chambre}_{date}_{heure}_{machine}.pdf"
    pdf.output(pdf_file)

    with open(pdf_file, "rb") as f:
        pdf_bytes = f.read()
    os.remove(pdf_file)
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={pdf_file}'
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
