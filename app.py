# -*- coding: utf-8 -*-
"""
Created on Wed Apr 23 01:20:47 2025

@author: agutierrez752
"""

# app.py (Backend con Flask)
from flask import Flask, request, jsonify
import google.generativeai as genai
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
import base64
import io
import os
import json
from dotenv import load_dotenv



# Configuro Firebase usando variables de entorno
firebase_creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if not firebase_creds_json:
    raise ValueError("No se encontró la configuración de Firebase en las variables de entorno")

# Convertir el string JSON a un diccionario
firebase_creds_dict = json.loads(firebase_creds_json)

# Configurar Firebase con las credenciales
cred = credentials.Certificate(firebase_creds_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Configura Gemini con variable de entorno
gemini_api_key = os.getenv('API_KEY')
if not gemini_api_key:
    raise ValueError("No se encontró la API Key de Gemini en las variables de entorno")

genai.configure(api_key=gemini_api_key)

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload():
    # 1. Recibir imagen desde el frontend (en base64)
    image_data = request.json['image'].split(',')[1]
    image = Image.open(io.BytesIO(base64.b64decode(image_data)))

    # 2. Generar descripción con Gemini
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([
        "Describe este objeto para venderlo online. Destaca detalles clave.",
        image
    ])
    description = response.text

    # 3. Guardar en Firebase
    doc_ref = db.collection('productos').add({
        'descripcion': description,
        'precio': request.json['precio'],  # Frontend enviará esto
        'imagen': image_data,  # Guardamos la imagen en base64
        'fecha': firestore.SERVER_TIMESTAMP
    })

    return jsonify({"id": doc_ref.id, "descripcion": description})

if __name__ == '__main__':
    app.run(debug=True)