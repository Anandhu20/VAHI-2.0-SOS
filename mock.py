import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
load_dotenv()

# Email details
email = os.getenv('EMAIL_ID')
app_password = os.getenv('EMAIL_PASSWORD')  # Use the App Password, not your regular password
recipient_email = os.getenv('EMAIL_RECIPIENT')

# Create the email
msg = MIMEMultipart()
msg['From'] = email
msg['To'] = recipient_email
msg['Subject'] = "Test Email with App Password"

body = "This is a test email sent from Python using an App Password."
msg.attach(MIMEText(body, 'plain'))

# Send the email
try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()  # Start TLS for security
    server.login(email, app_password)  # Use App Password here
    server.sendmail(email, recipient_email, msg.as_string())
    print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
finally:
    server.quit()
