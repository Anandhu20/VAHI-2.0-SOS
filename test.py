from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from werkzeug.security import generate_password_hash
import smtplib
import logging
import os
from dotenv import load_dotenv
from math import radians, sin, cos, sqrt, atan2

# Load environment variables
load_dotenv()
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure CORS correctly
CORS(app, resources={
    r"/*": {
        "origins": ["http://127.0.0.1:5500", "http://localhost:5500"],
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize database
db = SQLAlchemy(app)

class RegisteredUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<RegisteredUser {self.name}>"

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

@app.route('/register', methods=['POST'])
def register_user():
    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'message': 'Request must be JSON'
            }), 400

        data = request.get_json()
        required_fields = ['name', 'email', 'password', 'latitude', 'longitude']
        
        if not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400

        # Check for existing user
        if RegisteredUser.query.filter_by(email=data['email']).first():
            return jsonify({
                'success': False,
                'message': 'Email already registered'
            }), 409

        # Create new user
        new_user = RegisteredUser(
            name=data['name'],
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            latitude=float(data['latitude']),
            longitude=float(data['longitude'])
        )

        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Registration successful'
        }), 201

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Server error during registration'
        }), 500

@app.route('/get_helpers', methods=['GET'])
def get_helpers():
    try:
        helpers = RegisteredUser.query.filter_by(is_active=True).all()
        helpers_list = [{
            'id': helper.id,
            'name': helper.name,
            'email': helper.email,
            'latitude': helper.latitude,
            'longitude': helper.longitude
        } for helper in helpers]
        
        return jsonify({
            'success': True,
            'helpers': helpers_list
        })
    except Exception as e:
        logger.error(f"Error fetching helpers: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch helpers'
        }), 500
@app.route('/get_nearby_police_station')
def get_nearby_police_station():
    try:
        # Get coordinates from request parameters
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))

        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return jsonify({
                'success': False,
                'error': 'Invalid coordinates'
            }), 400

        # Use Google Places API to find nearby police stations
        url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
        params = {
            'location': f'{lat},{lng}',
            'radius': '5000',  # Search within 5km
            'type': 'police',
            'key': GOOGLE_MAPS_API_KEY
        }

        response = requests.get(url, params=params)
        data = response.json()

        if data.get('status') != 'OK':
            return jsonify({
                'success': False,
                'error': 'No police stations found nearby'
            }), 404

        # Get the closest police station
        closest_station = data['results'][0]
        station_location = closest_station['geometry']['location']

        # Get additional details about the police station
        place_details_url = 'https://maps.googleapis.com/maps/api/place/details/json'
        details_params = {
            'place_id': closest_station['place_id'],
            'fields': 'name,formatted_phone_number,formatted_address',
            'key': GOOGLE_MAPS_API_KEY
        }

        details_response = requests.get(place_details_url, params=details_params)
        details_data = details_response.json()

        if details_data.get('status') != 'OK':
            phone = 'Not available'
        else:
            phone = details_data['result'].get('formatted_phone_number', 'Not available')

        # Calculate distance
        distance = get_distance(lat, lng, 
                              station_location['lat'], 
                              station_location['lng'])

        return jsonify({
            'success': True,
            'policeStation': {
                'name': closest_station['name'],
                'lat': station_location['lat'],
                'lng': station_location['lng'],
                'phone': phone,
                'distance': round(distance, 2),  # Distance in km
                'address': details_data['result'].get('formatted_address', 'Address not available')
            }
        })

    except Exception as e:
        print(f"Error in get_nearby_police_station: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch police station information'
        }), 500
@app.route('/send_sos', methods=['POST'])
def send_sos():
    try:
        data = request.get_json()
        if not data or 'location' not in data:
            return jsonify({
                'success': False,
                'message': 'No location data provided'
            }), 400

        sender_location = data['location']
        radius = float(os.getenv('SOS_RADIUS', '10'))  # 10km default radius
        helpers = RegisteredUser.query.filter_by(is_active=True).all()
        emails_sent = 0

        for helper in helpers:
            distance = calculate_distance(
                float(sender_location['latitude']),
                float(sender_location['longitude']),
                helper.latitude,
                helper.longitude
            )
            
            if distance <= radius:
                if send_sos_email(helper.email, sender_location, distance):
                    emails_sent += 1

        return jsonify({
            'success': True,
            'message': f'SOS sent to {emails_sent} helpers',
            'helpersNotified': emails_sent
        })

    except Exception as e:
        logger.error(f"SOS error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to send SOS'
        }), 500

def send_sos_email(recipient_email, location, distance):
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv('EMAIL_USER')
        msg['To'] = recipient_email
        msg['Subject'] = "URGENT: SOS Signal Received"

        body = f"""
        URGENT: SOS signal received from {distance:.2f}km away!

        Location: https://www.google.com/maps?q={location['latitude']},{location['longitude']}

        Please respond if you can help.
        """

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(
                os.getenv('EMAIL_USER'),
                os.getenv('EMAIL_PASSWORD')
            )
            server.send_message(msg)

        return True
    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return False

@app.route('/get_location_info', methods=['POST'])
def get_location_info():
    try:
        data = request.get_json()
        if not all(k in data for k in ['lat', 'lng']):
            return jsonify({
                'success': False,
                'message': 'Missing coordinates'
            }), 400

        geolocator = Nominatim(user_agent="distress_signal_app")
        try:
            location = geolocator.reverse((data['lat'], data['lng']))
            address = location.address if location else "Address not found"
        except GeocoderTimedOut:
            address = "Timeout getting address"

        return jsonify({
            'success': True,
            'address': address,
            'coordinates': {
                'latitude': data['lat'],
                'longitude': data['lng']
            }
        })
    except Exception as e:
        logger.error(f"Location error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get location info'
        }), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)