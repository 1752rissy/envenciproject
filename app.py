# -*- coding: utf-8 -*-
"""
Backend refactorizado para Envenci
Endpoints separados para generación de descripción y publicación de productos
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
import base64
import io
import os
import json
from dotenv import load_dotenv

# Cargar variables de entorno para desarrollo local
load_dotenv()

# Configuración de Firebase
def configure_firebase():
    """Configura y devuelve la conexión a Firestore"""
    firebase_creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not firebase_creds_json:
        raise ValueError("Configuración de Firebase no encontrada en variables de entorno")
    
    firebase_creds_dict = json.loads(firebase_creds_json)
    cred = credentials.Certificate(firebase_creds_dict)
    
    # Especifica el nombre de tu base de datos en la configuración
    firebase_admin.initialize_app(cred, {
        'projectId': 'evenci-41812',
        'databaseURL': 'https://evencidata.firebaseio.com'  # Asegúrate de usar la URL correcta
    })
    
    return firestore.client()

# Configuración de Gemini AI
def configure_gemini():
    """Configura y devuelve el cliente de Gemini"""
    gemini_api_key = os.getenv('API_KEY')
    if not gemini_api_key:
        raise ValueError("API Key de Gemini no encontrada en variables de entorno")
    
    genai.configure(api_key=gemini_api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

# Inicialización de servicios
db = configure_firebase()
gemini_model = configure_gemini()
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas las rutas

# Helpers
def decode_image(image_data):
    """Decodifica imagen base64 a objeto PIL.Image"""
    if ',' in image_data:  # Remover prefijo data:image si existe
        image_data = image_data.split(',')[1]
    return Image.open(io.BytesIO(base64.b64decode(image_data)))

# Endpoints
@app.route('/api/generate-description', methods=['POST'])
def generate_description():
    """Endpoint para generación de descripciones con Gemini AI"""
    try:
        if 'image' not in request.json:
            return jsonify({"error": "Se requiere una imagen"}), 400
            
        image = decode_image(request.json['image'])
        
        # Generar descripción con Gemini
        response = gemini_model.generate_content([
            "Genera una descripción detallada para vender este producto online.",
            "Incluye características clave, materiales y condición.",
            "Sé conciso pero persuasivo (máx 200 caracteres).",
            image
        ])
        
        return jsonify({
            "description": response.text,
            "status": "success"
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

@app.route('/api/publish-product', methods=['POST'])
def publish_product():
    """Endpoint para publicación de productos en Firestore"""
    try:
        required_fields = ['image', 'description', 'price']
        if not all(field in request.json for field in required_fields):
            return jsonify({"error": "Faltan campos requeridos"}), 400
            
        # Validar precio
        try:
            price = float(request.json['price'])
            if price <= 0:
                raise ValueError("El precio debe ser mayor a 0")
        except ValueError:
            return jsonify({"error": "Precio inválido"}), 400
            
        # Publicar en Firestore
        doc_ref = db.collection('products').add({
            'description': request.json['description'],
            'price': price,
            'image': request.json['image'],
            'created_at': firestore.SERVER_TIMESTAMP,
            'status': 'active'
        })
        
        return jsonify({
            "product_id": doc_ref.id,
            "status": "success"
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

if __name__ == '__main__':
    app.run(debug=True)