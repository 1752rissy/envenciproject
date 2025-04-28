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
from firebase_admin import credentials, firestore, storage
import base64
import io
import os
import json
import uuid
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno para desarrollo local
load_dotenv()

# Configuración de Firebase
def configure_firebase():
    """Configura y devuelve la conexión a Firestore y Storage"""
    firebase_creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not firebase_creds_json:
        raise ValueError("Configuración de Firebase no encontrada en variables de entorno")
    
    firebase_creds_dict = json.loads(firebase_creds_json)
    cred = credentials.Certificate(firebase_creds_dict)
    
    # Verifica si Firebase ya está inicializado
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'projectId': 'evenci-41812',
            'storageBucket': 'evenci-41812-storage'  # Nombre del bucket
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
bucket = storage.bucket()  # Referencia al bucket de Firebase Storage
gemini_model = configure_gemini()
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas las rutas

# Helpers
def decode_image(image_data):
    """Decodifica imagen base64 a objeto PIL.Image"""
    if ',' in image_data:  # Remover prefijo data:image si existe
        image_data = image_data.split(',')[1]
    return Image.open(io.BytesIO(base64.b64decode(image_data)))

def generate_signed_url(bucket_name, file_name):
    """Genera una URL firmada para un archivo en Firebase Storage"""
    try:
        blob = bucket.blob(file_name)

        # Generar URL firmada con un tiempo de expiración (por ejemplo, 1 hora)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),  # Tiempo de expiración de la URL
            method="GET"
        )
        return url
    except Exception as e:
        print(f"Error al generar la URL firmada para el archivo {file_name}: {e}")
        return None

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
            "Sé conciso pero persuasivo (máx 200 caracteres). Mostra la descripcion generada directamente sin ningun comentario extra de tu parte.",
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

        # Decodificar la imagen Base64
        image_data = request.json['image']
        if not isinstance(image_data, str):
            return jsonify({"error": "El campo 'image' debe ser una cadena serializable"}), 400

        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]  # Remover prefijo data:image
        image_bytes = base64.b64decode(image_data)

        # Generar un nombre único para la imagen
        file_name = f"images/{uuid.uuid4()}.png"
        blob = bucket.blob(file_name)

        # Subir la imagen al bucket
        blob.upload_from_string(image_bytes, content_type='image/png')

        # Generar una URL firmada
        image_url = generate_signed_url('evenci-41812-storage', file_name)

        # Crear un nuevo documento con un ID generado automáticamente
        doc_ref = db.collection('products').document()
        doc_id = doc_ref.id

        # Guardar los datos en Firestore
        doc_ref.set({
            'description': request.json['description'],
            'price': price,
            'image_file_name': file_name,  # Guardar solo el nombre del archivo
            'created_at': firestore.SERVER_TIMESTAMP,
            'status': 'active'
        })

        # Devolver solo el ID del documento (serializable)
        return jsonify({
            "product_id": doc_id,
            "status": "success"
        })
        
    except Exception as e:
        # Depuración adicional para identificar el origen del error
        print(f"Error interno: {e}")
        return jsonify({
            "error": "Ocurrió un error al procesar la solicitud",
            "details": str(e),
            "status": "error"
        }), 500

@app.route('/api/get-products', methods=['GET'])
def get_products():
    """Endpoint para obtener la lista de productos"""
    try:
        # Consultar todos los productos en la colección 'products'
        products_ref = db.collection('products')
        products = products_ref.order_by('created_at', direction=firestore.Query.DESCENDING).stream()

        # Convertir los documentos en una lista de diccionarios
        product_list = []
        for doc in products:
            product_data = doc.to_dict()
            product_data['id'] = doc.id  # Añadir el ID del documento

            # Regenerar la URL firmada usando el nombre del archivo almacenado
            file_name = product_data.get('image_file_name')
            if file_name:
                new_image_url = generate_signed_url('evenci-41812-storage', file_name)
                if new_image_url:
                    product_data['image'] = new_image_url
                else:
                    print(f"No se pudo generar la URL firmada para el archivo {file_name}")
            else:
                print(f"No se encontró el nombre del archivo para el producto {doc.id}")

            product_list.append(product_data)

        return jsonify({
            "products": product_list,
            "status": "success"
        })

    except Exception as e:
        print(f"Error interno: {e}")
        return jsonify({
            "error": "Ocurrió un error al obtener los productos",
            "details": str(e),
            "status": "error"
        }), 500

if __name__ == '__main__':
    app.run(debug=True)