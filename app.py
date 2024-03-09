from flask import Flask, request, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS 
import config

app = Flask(__name__)
CORS(app)

# Apply configurations from config.py
app.config.update(config.MAIL_CONFIG)

# Configure your mail settings
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True

mail = Mail(app)


@app.route("/contact_us_email", methods=["POST"])
def send_email():
    data = request.json
    msg = Message(
        "Contact Form Submission from Cronos",
        sender="joshsparkes6@gmail.com",
        recipients=["joshsparkes6@gmail.com", "nick_castrioty@hotmail.com"],
    )
    msg.body = f"""
    Name: {data.get('firstName')} {data.get('surname')}
    Company: {data.get('companyName')}
    Email: {data.get('email')}
    Website: {data.get('website')}
    Message: {data.get('message')}
    """
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")
        return jsonify({"message": "Failed to send email", "error": str(e)}), 500

    return jsonify({"message": "Email sent successfully"}), 200


if __name__ == "__main__":
    app.run(debug=True)
