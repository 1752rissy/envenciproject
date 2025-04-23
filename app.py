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

# Configura Firebase
cred = credentials.Certificate("firebase-creds.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Configura Gemini
genai.configure(api_key="AIzaSyDy1yTofHLoQ7AirwUMSp2jWiO6kyYIY48")

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