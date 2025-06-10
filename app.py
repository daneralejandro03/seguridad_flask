import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from azure.communication.email import EmailClient
from dotenv import load_dotenv, find_dotenv
from flask_cors import CORS

# Carga .env **solo** si no hay DATABASE_URL en el entorno
if not os.getenv("DATABASE_URL"):
    load_dotenv(find_dotenv(), override=False)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)
CORS(app)

# Mostrar en logs qué URI de BD estamos usando
logging.info("Conectando a la base de datos: %s", os.getenv("DATABASE_URL"))

# Configuración de la base de datos
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Modelo de la tabla 'ruta1'
class Ruta(db.Model):
    __tablename__ = "ruta1"
    id = db.Column(db.Integer, primary_key=True)
    latitud = db.Column(db.String(50), nullable=False)
    longitud = db.Column(db.String(50), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False)
    ip = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(255))
    maps_url = db.Column(db.String(255))

    def __repr__(self):
        return f"<Ruta {self.id} @ {self.fecha_hora}>"

# Crear tablas (en producción usa migraciones)
with app.app_context():
    db.create_all()

@app.route("/send", methods=["GET"])
def send_data():
    try:
        # Parámetros
        lat = request.args.get("lat", "")
        lon = request.args.get("long", "")
        agent = request.args.get("agent", "")
        ip = request.remote_addr or "N/A"
        fecha = datetime.utcnow()

        if not lat or not lon:
            return jsonify({"error": "Faltan parámetros de latitud o longitud."}), 400

        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}"

        # Guardar en base de datos
        nueva_ruta = Ruta(
            latitud=lat,
            longitud=lon,
            fecha_hora=fecha,
            ip=ip,
            user_agent=agent,
            maps_url=maps_url
        )
        db.session.add(nueva_ruta)
        db.session.commit()
        logging.info("Datos guardados en la tabla 'ruta1' con id %s", nueva_ruta.id)

        # Generar HTML para log y correo
        html_data = (
            f"<pre>"
            f"Datetime: {fecha.strftime('%d-%m-%Y %H:%M:%S (UTC)')}\n"
            f"IP: {ip}\n"
            f"Location: <a href='{maps_url}' target='_blank'>Click Here</a>\n"
            f"User-Agent: {agent}\n"
            f"</pre>\n\n"
        )

        # Escribir en log.html
        with open("log.html", "a", encoding="utf-8") as log_file:
            log_file.write(html_data)
        logging.info("Datos registrados en log.html")

    except Exception as e:
        logging.error("Error al procesar datos: %s", e)
        return jsonify({"error": str(e)}), 500

    try:
        # Envío de correo
        connection_string   = os.environ.get("CONNECTION_STRING")
        sender_address      = os.environ.get("SENDER_ADDRESS")
        recipient_addresses = os.environ.get("RECIPIENT_ADDRESS")

        if not all([connection_string, sender_address, recipient_addresses]):
            raise ValueError("Variables de entorno de correo faltantes.")

        recipients_list = [email.strip() for email in recipient_addresses.split(",")]
        email_client = EmailClient.from_connection_string(connection_string)
        message = {
            "senderAddress": sender_address,
            "recipients": {"to": [{"address": e} for e in recipients_list]},
            "content": {
                "subject": "Alerta de ubicación recibida",
                "html": html_data,
            }
        }

        poller = email_client.begin_send(message)
        result = poller.result()
        logging.info("Correo enviado exitosamente. ID: %s", result.get("id"))

    except Exception as ex:
        logging.error("Error al enviar el correo: %s", ex)
        return jsonify({"error": f"Error al enviar email: {ex}"}), 500

    return jsonify({"message": "Datos guardados, log y correo realizados."}), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=10000)
