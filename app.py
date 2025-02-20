import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from azure.communication.email import EmailClient
from dotenv import load_dotenv
from flask_cors import CORS

# Cargar variables de entorno desde .env
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

@app.route('/send', methods=['GET'])
def send_data():
    """
    Endpoint que recibe datos de ubicación vía GET, los registra en un archivo HTML y envía un correo con la información.
    """
    try:
        # Obtener parámetros desde la petición GET
        lat = request.args.get('lat', '')
        lon = request.args.get('long', '')
        agent = request.args.get('agent', '')
        ip = request.remote_addr or 'N/A'
        date_str = datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S (UTC)")

        # Validar que se envíen latitud y longitud
        if not lat or not lon:
            return jsonify({"error": "Faltan parámetros de latitud o longitud."}), 400

        # Construir la URL para Google Maps
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}"

        # Preparar los datos en formato HTML
        html_data = (
            f"<pre>"
            f"Datetime: {date_str}\n"
            f"IP: {ip}\n"
            f"Location: <a href='{maps_url}' target='_blank'>Click Here</a>\n"
            f"User-Agent: {agent}\n"
            f"</pre>\n\n"
        )

        # Escribir en el archivo de log
        with open("log.html", "a", encoding="utf-8") as log_file:
            log_file.write(html_data)
        logging.info("Datos registrados en log.html")

    except Exception as e:
        logging.error("Error al registrar los datos: %s", e)
        return jsonify({"error": f"Error al escribir en el log: {e}"}), 500

    try:
        # Obtener datos desde las variables de entorno
        connection_string = os.environ.get("CONNECTION_STRING")
        sender_address = os.environ.get("SENDER_ADDRESS")
        recipient_addresses = os.environ.get("RECIPIENT_ADDRESS")

        # Validar que todas las variables necesarias estén definidas
        if not all([connection_string, sender_address, recipient_addresses]):
            raise ValueError("Una o más variables de entorno requeridas no están definidas.")

        # Convertir la cadena de correos en una lista, separando por comas
        recipients_list = [email.strip() for email in recipient_addresses.split(',')]

        logging.info("Conexión a Azure establecida. Enviando correo de %s a %s", sender_address, recipients_list)

        # Inicializar el cliente de correo
        email_client = EmailClient.from_connection_string(connection_string)

        # Configurar el mensaje de correo con múltiples destinatarios
        message = {
            "senderAddress": sender_address,
            "recipients": {
                "to": [{"address": email} for email in recipients_list],
            },
            "content": {
                "subject": "Alerta de ubicación recibida",
                "html": html_data,
            }
        }

        # Enviar el correo
        logging.info("Enviando correo...")
        poller = email_client.begin_send(message)
        result = poller.result()  # Espera a que se envíe el correo
        logging.info("Correo enviado exitosamente. ID: %s", result.get("id"))

    except Exception as ex:
        logging.error("Error al enviar el correo: %s", ex)
        return jsonify({"error": f"Error al enviar el correo electrónico: {ex}"}), 500

    return jsonify({"message": "Datos recibidos, log actualizado y correo enviado."}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
