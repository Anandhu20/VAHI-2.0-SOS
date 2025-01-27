import smtplib
import math
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory,send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from math import radians, sin, cos, sqrt, atan2
import logging

import os
from dotenv import load_dotenv
load_dotenv()
from flask_cors import CORS


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST"])
# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Ensure database file is 'users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Create the database
with app.app_context():
    db.create_all()
    print("Database and tables created successfully!")
CORS(app, resources={
    r"/*": {
        "origins": ["http://127.0.0.1:5500", "http://localhost:5500"],
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept"],
        "supports_credentials": True  # Changed from allow_credentials
    }
})

# Database Model for Registered Users
class RegisteredUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<RegisteredUser {self.name}, {self.email}>"
# File to store user data
USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# Route to render the index page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/audio-file')
def serve_audio():
    return send_file('/static/audio/alarm.mp3', as_attachment=False)

@app.route('/helpers')
def helpers_page():
    return render_template('index11.html')

@app.route('/get_helpers', methods=['GET'])
def get_helpers():
    try:
        helpers = RegisteredUser.query.all()
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
        print(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch helpers'
        }), 500

@app.route('/delete_helper/<int:helper_id>', methods=['DELETE'])
def delete_helper(helper_id):
    try:
        helper = RegisteredUser.query.get(helper_id)
        if helper:
            db.session.delete(helper)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Helper deleted successfully'})
        return jsonify({'success': False, 'message': 'Helper not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# Route to show address
@app.route('/get_location_info', methods=['POST'])
def get_location_info():
    try:
        data = request.json
        latitude = data.get('lat')
        longitude = data.get('lng')
        
        if latitude is None or longitude is None:
            return jsonify({'success': False, 'error': 'Missing coordinates'}), 400

        # Initialize the geolocator
        geolocator = Nominatim(user_agent="distress_signal_app")
        
        try:
            # Get the address
            location = geolocator.reverse((latitude, longitude), language='en')
            address = location.address if location else "Address not found"
        except GeocoderTimedOut:
            address = "Timeout getting address"
        except Exception as e:
            address = f"Error getting address: {str(e)}"

        return jsonify({
            'success': True,
            'address': address,
            'coordinates': {
                'latitude': latitude,
                'longitude': longitude
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Route to send SOS
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in kilometers

    # Precise conversion and calculation
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat/2)**2 + 
         math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance

def get_helpers_from_database():
    # Query actual helpers from the database
    try:
        helpers = RegisteredUser.query.all()
        return [{
            'id': helper.id,
            'email': helper.email,
            'latitude': helper.latitude,
            'longitude': helper.longitude
        } for helper in helpers]
    except Exception as e:
        logger.error(f"Error fetching helpers from database: {str(e)}")
        return []

def get_nearby_helpers(user_lat, user_lon, radius=10):
    try:
        helpers = RegisteredUser.query.all()
        nearby_helpers = []
        
        print(f"Searching helpers near: {user_lat}, {user_lon}")
        
        for helper in helpers:
            distance = calculate_distance(
                float(user_lat), 
                float(user_lon),
                float(helper.latitude),
                float(helper.longitude)
            )
            
            print(f"Helper Location: {helper.latitude}, {helper.longitude}")
            print(f"Calculated Distance: {distance} km")
            
            if distance <= radius:
                nearby_helpers.append({
                    'id': helper.id,
                    'email': helper.email,
                    'distance': round(distance, 2)
                })
        
        print(f"Found {len(nearby_helpers)} nearby helpers")
        return nearby_helpers
    except Exception as e:
        print(f"Helper search error: {str(e)}")
        return []


# Email configuration
# def send_sos_email(helper_email, location_info, distance):
#     # Email credentials - store these in your .env file
#     SMTP_SERVER = "smtp.gmail.com"  # or your email provider's SMTP server
#     SMTP_PORT = 587
#     SENDER_EMAIL = os.getenv('EMAIL_USER')  # add this to your .env file
#     SENDER_PASSWORD = os.getenv('EMAIL_PASSWORD')  # add this to your .env file

#     try:
#         # Create message
#         msg = MIMEMultipart()
#         msg['From'] = SENDER_EMAIL
#         msg['To'] = helper_email
#         msg['Subject'] = "URGENT: SOS Signal Received"

#         # Email body
#         body = f"""
#         URGENT: An SOS signal has been received from someone nearby!

#         Location Details:
#         - Latitude: {location_info['latitude']}
#         - Longitude: {location_info['longitude']}
#         - Approximate distance from you: {distance:.2f} km

#         Google Maps Link:
#         https://www.google.com/maps?q={location_info['latitude']},{location_info['longitude']}

#         This person needs immediate assistance. Please check their location and respond if you can help.

#         Note: This is an automated message. Please be cautious and ensure your own safety first.
#         """

#         msg.attach(MIMEText(body, 'plain'))

#         # Create SMTP session
#         server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
#         server.starttls()
#         server.login(SENDER_EMAIL, SENDER_PASSWORD)

#         # Send email
#         server.send_message(msg)
#         server.quit()
        
#         logger.info(f"SOS email sent successfully to {helper_email}")
#         return True

#     except Exception as e:
#         logger.error(f"Failed to send email to {helper_email}: {str(e)}")
#         return False

# # Update the send_sos route to include email notifications
# # Route to send SOS

# Update email configuration
EMAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': os.getenv('EMAIL_USER'),
    'MAIL_PASSWORD': os.getenv('EMAIL_PASSWORD')
}

def send_sos_email(recipient, location, distance):
    try:
        # Validate credentials
        if not EMAIL_CONFIG['MAIL_USERNAME'] or not EMAIL_CONFIG['MAIL_PASSWORD']:
            raise ValueError("Email credentials missing")

        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['MAIL_USERNAME']
        msg['To'] = recipient
        msg['Subject'] = "EMERGENCY SOS ALERT!"

        # Create body with string (not bytes)
        body = f"""
        EMERGENCY ALERT - Someone needs help!
        
        Location Details:
        Latitude: {location['latitude']}
        Longitude: {location['longitude']}
        Distance from you: {distance:.2f} km
        
        Google Maps Link:
        https://www.google.com/maps?q={location['latitude']},{location['longitude']}
        
        Please respond if you can help!
        """

        msg.attach(MIMEText(body, 'plain'))

        # Send email
        with smtplib.SMTP(EMAIL_CONFIG['MAIL_SERVER'], EMAIL_CONFIG['MAIL_PORT']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['MAIL_USERNAME'], EMAIL_CONFIG['MAIL_PASSWORD'])
            server.send_message(msg)
            return True

    except Exception as e:
        logger.error(f"Email error to {recipient}: {str(e)}")
        return False

# Update send_sos route to use new email function
@app.route('/send_sos', methods=['POST'])
def send_sos():
    try:
        data = request.get_json()
        user_location = data['location']
        
        nearby_helpers = get_nearby_helpers(
            user_location['latitude'],
            user_location['longitude']
        )
        
        emails_sent = 0
        for helper in nearby_helpers:
            if send_sos_email(helper['email'], user_location, helper['distance']):
                emails_sent += 1

        return jsonify({
            'success': True,
            'helpersNotified': emails_sent
        })

    except Exception as e:
        logger.error(f"SOS Error: {str(e)}")
        return jsonify({
            'success': False, 
            'message': str(e)
        }), 500
# Route to register a user
@app.route('/register_user', methods=['POST'])
def register_user():
    try:
        # Ensure the request contains JSON data
        if request.is_json:  # Check if the incoming request is JSON
            data = request.get_json()
        else:
            return jsonify({'success': False, 'message': 'Request must be in JSON format'}), 400
        
        # Extract user details from the request
        name = data.get('name')
        email = data.get('email')
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        # Validate input fields
        if not all([name, email, latitude, longitude]):
            return jsonify({'success': False, 'message': "All fields (name, email, latitude, longitude) are required!"}), 400

        # Check if latitude and longitude are valid numbers
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except ValueError:
            return jsonify({'success': False, 'message': "Latitude and Longitude must be numeric values"}), 400

        # Check for duplicate email
        existing_user = RegisteredUser.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': "This email is already registered."}), 409  # Conflict status code

        # Add user to the database
        new_user = RegisteredUser(name=name, email=email, latitude=latitude, longitude=longitude)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({'success': True, 'message': "User registered successfully!"}), 201  # Created status code

    except Exception as e:
        # Log the exception (for debugging) and return a server error
        print(f"Error occurred: {str(e)}")  # For debugging; remove in production
        return jsonify({'success': False, 'message': "Internal server error. Please try again later."}), 500

# Route to display helpers
@app.route('/view_helpers')
def view_helpers():
    helpers = Helper.query.all()
    return render_template('helpers.html', helpers=helpers)

if __name__ == '__main__':
    app.run(debug=True,port=5000)