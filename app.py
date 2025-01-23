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
    return render_template('index11.html')

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
    R = 6371  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)*2 + cos(lat1) * cos(lat2) * sin(dlon/2)*2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


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
        
        for helper in helpers:
            distance = calculate_distance(
                float(user_lat), 
                float(user_lon),
                float(helper.latitude),
                float(helper.longitude)
            )
            
            if distance <= radius:
                nearby_helpers.append({
                    'id': helper.id,
                    'email': helper.email,
                    'distance': round(distance, 2)
                })
        
        return nearby_helpers
    except Exception as e:
        app.logger.error(f"Helper search error: {str(e)}")
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
@app.route('/send_sos', methods=['POST'])
def send_sos():
    try:
        # Get location data from the request
        data = request.get_json()
        user_location = data['location']

        # Get nearby helpers
        helpers = get_nearby_helpers(
            user_location['latitude'],
            user_location['longitude']
        )
        
        if not data or 'location' not in data:
            return jsonify({
                'success': False,
                'message': 'No location data provided',
                'helpersNotified': 0
            }), 400

        sender_location = data['location']
        radius = data.get('radius', 10)  # 10km default radius

        # Get helpers from database
        helpers = get_helpers_from_database()
        nearby_helpers = []
        emails_sent = 0

        # Email credentials
        sender_email = os.getenv('EMAIL_ID')
        app_password = os.getenv('EMAIL_PASSWORD')

        # Find nearby helpers and send emails
        for helper in helpers:
            try:
                distance = calculate_distance(
                    float(sender_location['latitude']),
                    float(sender_location['longitude']),
                    float(helper['latitude']),
                    float(helper['longitude'])
                )
                
                if distance <= radius:
                    nearby_helpers.append(helper)
                    
                    # Create email for this helper
                    msg = MIMEMultipart()
                    msg['From'] = sender_email
                    msg['To'] = helper['email']
                    msg['Subject'] = "SOS - Emergency Alert!"

                    # Email body with location and distance
                    body = f"""
                    EMERGENCY ALERT - SOS Signal Received!
                    
                    Someone nearby needs immediate help!
                    
                    Location Details:
                    Latitude: {sender_location['latitude']}
                    Longitude: {sender_location['longitude']}
                    Distance from you: {distance:.2f} km
                    
                    Google Maps Link: https://www.google.com/maps?q={sender_location['latitude']},{sender_location['longitude']}
                    
                    Please respond if you're able to help!
                    """
                    
                    msg.attach(MIMEText(body, 'plain'))

                    # Send email
                    try:
                        server = smtplib.SMTP('smtp.gmail.com', 587)
                        server.starttls()
                        server.login(sender_email, app_password)
                        server.sendmail(sender_email, helper['email'], msg.as_string())
                        server.quit()
                        emails_sent += 1
                        logger.info(f"Email sent to helper at distance {distance}km")
                    except Exception as email_error:
                        logger.error(f"Failed to send email to {helper['email']}: {str(email_error)}")
                        continue
                    
            except Exception as e:
                logger.error(f"Error processing helper {helper['id']}: {str(e)}")
                continue

        return jsonify({
            'success': True,
            'message': f'SOS signal sent successfully to {emails_sent} helpers',
            'helpersNotified': emails_sent,
            'radius': radius,
            'location': sender_location
        })

    except Exception as e:
        logger.error(f"Error processing SOS request: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}',
            'helpersNotified': 0
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