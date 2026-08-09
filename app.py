"""
TKM Barbearia — App de Agendamento
Backend: Python (Flask + SQLite)
Frontend: HTML/CSS/JavaScript (em /static e /templates)

Como rodar:
    pip install -r requirements.txt
    python app.py
Depois abra: http://127.0.0.1:5000
"""

import base64
import io
import random
import re
import sqlite3
import string
from datetime import datetime, timedelta

import qrcode
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

DB_PATH = "tkm.db"

# ---------------------------------------------------------------------------
# Regras do negócio
# ---------------------------------------------------------------------------
# datetime.weekday(): Segunda=0, Terça=1, Quarta=2, Quinta=3, Sexta=4, Sábado=5, Domingo=6
CLOSED_WEEKDAYS = {0, 6}          # Segunda e Domingo fechados
LOW_PRICE_WEEKDAYS = {0, 1, 2}    # Segunda a Quarta -> R$25
LOW_PRICE = 25
HIGH_PRICE = 65
OPEN_HOUR = 7
CLOSE_HOUR = 18
SLOT_MINUTES = 30

DOW_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MONTHS_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def all_time_slots():
    """Gera todos os horários possíveis de OPEN_HOUR até CLOSE_HOUR (não inclusive)."""
    slots = []
    t = datetime.strptime(f"{OPEN_HOUR:02d}:00", "%H:%M")
    end = datetime.strptime(f"{CLOSE_HOUR:02d}:00", "%H:%M")
    while t < end:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=SLOT_MINUTES)
    return slots


TIME_SLOTS = all_time_slots()


def price_for_date(date_obj):
    return LOW_PRICE if date_obj.weekday() in LOW_PRICE_WEEKDAYS else HIGH_PRICE


def is_closed(date_obj):
    return date_obj.weekday() in CLOSED_WEEKDAYS


def normalize_phone(phone):
    return re.sub(r"\D", "", phone or "")


def gen_code():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem caracteres ambíguos
    return "".join(random.choice(chars) for _ in range(6))


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(date, time)
        )
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# QR Code
# ---------------------------------------------------------------------------
def make_qr_base64(payload_text):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(payload_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#171310", back_color="#f3ead8")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def qr_payload(booking_row):
    date_obj = datetime.strptime(booking_row["date"], "%Y-%m-%d")
    label = f"{DOW_PT[date_obj.weekday()]}, {date_obj.day} de {MONTHS_PT[date_obj.month - 1]}"
    return (
        f"TKM BARBEARIA\n"
        f"Codigo: {booking_row['code']}\n"
        f"Cliente: {booking_row['name']}\n"
        f"Data: {label}\n"
        f"Horario: {booking_row['time']}\n"
        f"Valor: R${booking_row['price']}"
    )


def booking_to_dict(row, with_qr=True):
    data = {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "phone": row["phone"],
        "date": row["date"],
        "time": row["time"],
        "price": row["price"],
    }
    if with_qr:
        data["qr_base64"] = make_qr_base64(qr_payload(row))
    return data


# ---------------------------------------------------------------------------
# Rotas de página
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.route("/api/config")
def api_config():
    return jsonify(
        {
            "openHour": OPEN_HOUR,
            "closeHour": CLOSE_HOUR,
            "slotMinutes": SLOT_MINUTES,
            "timeSlots": TIME_SLOTS,
            "closedWeekdays": sorted(CLOSED_WEEKDAYS),  # 0=Segunda ... 6=Domingo
            "lowPriceWeekdays": sorted(LOW_PRICE_WEEKDAYS),
            "lowPrice": LOW_PRICE,
            "highPrice": HIGH_PRICE,
        }
    )


@app.route("/api/slots")
def api_slots():
    date_str = request.args.get("date", "")
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Data inválida"}), 400

    db = get_db()
    rows = db.execute(
        "SELECT time FROM bookings WHERE date = ?", (date_str,)
    ).fetchall()
    taken = [r["time"] for r in rows]

    return jsonify(
        {
            "date": date_str,
            "closed": is_closed(date_obj),
            "price": price_for_date(date_obj),
            "taken": taken,
            "allSlots": TIME_SLOTS,
        }
    )


@app.route("/api/book", methods=["POST"])
def api_book():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    date_str = (payload.get("date") or "").strip()
    time_str = (payload.get("time") or "").strip()

    if not name or not phone or not date_str or not time_str:
        return jsonify({"error": "Preencha todos os campos."}), 400

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Data inválida."}), 400

    if is_closed(date_obj):
        return jsonify({"error": "A barbearia está fechada nesse dia."}), 400

    if time_str not in TIME_SLOTS:
        return jsonify({"error": "Horário inválido."}), 400

    if date_obj.date() < datetime.now().date():
        return jsonify({"error": "Não é possível agendar em uma data passada."}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM bookings WHERE date = ? AND time = ?", (date_str, time_str)
    ).fetchone()
    if existing:
        return jsonify({"error": "Esse horário acabou de ser reservado. Escolha outro."}), 409

    price = price_for_date(date_obj)
    code = gen_code()
    # garante código único
    while db.execute("SELECT id FROM bookings WHERE code = ?", (code,)).fetchone():
        code = gen_code()

    created_at = datetime.now().isoformat()

    try:
        db.execute(
            """INSERT INTO bookings (code, name, phone, date, time, price, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, name, phone, date_str, time_str, price, created_at),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Esse horário acabou de ser reservado. Escolha outro."}), 409

    row = db.execute("SELECT * FROM bookings WHERE code = ?", (code,)).fetchone()
    return jsonify({"booking": booking_to_dict(row)}), 201


@app.route("/api/bookings")
def api_list_bookings():
    phone = normalize_phone(request.args.get("phone", ""))
    if not phone:
        return jsonify({"error": "Informe um telefone."}), 400

    db = get_db()
    rows = db.execute("SELECT * FROM bookings ORDER BY date, time").fetchall()
    matches = [r for r in rows if normalize_phone(r["phone"]) == phone]
    return jsonify({"bookings": [booking_to_dict(r) for r in matches]})


@app.route("/api/bookings/<code>", methods=["DELETE"])
def api_cancel_booking(code):
    phone = normalize_phone(request.args.get("phone", ""))
    db = get_db()
    row = db.execute("SELECT * FROM bookings WHERE code = ?", (code.upper(),)).fetchone()
    if not row:
        return jsonify({"error": "Agendamento não encontrado."}), 404
    if normalize_phone(row["phone"]) != phone:
        return jsonify({"error": "Telefone não confere com este agendamento."}), 403

    db.execute("DELETE FROM bookings WHERE code = ?", (code.upper(),))
    db.commit()
    return jsonify({"success": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
else:
    init_db()
