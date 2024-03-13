"""Backend of Chronos"""

import base64
from flask import Flask, request, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS
import requests
from firebase_admin import credentials, firestore, initialize_app
import openai
import config

app = Flask(__name__)
CORS(app)

# OpenAI key
openai.api_key = config.OPEN_AI_KEY

# Apply configurations from config.py
app.config.update(config.MAIL_CONFIG)

# Configure your mail settings
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True

mail = Mail(app)

# Initialize Firebase Admin
cred = credentials.Certificate("firebase_service_account.json")
initialize_app(cred)
db = firestore.client()


@app.route("/contact_us_email", methods=["POST"])
def send_email():
    """Send an email to Nick and Josh when form is filled in"""
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
    APIs: {data.get('apis')}
    """
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")
        return jsonify({"message": "Failed to send email", "error": str(e)}), 500

    return jsonify({"message": "Email sent successfully"}), 200


def fetch_file_contents(github_token, file_urls):
    """Fetching the contents of the defined repo files using GitHub API URLs"""
    headers = {"Authorization": f"token {github_token}"}
    file_contents = []

    for url in file_urls:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            response_json = response.json()
            # Check if "content" key exists in the JSON response
            if "content" in response_json:
                content_data = response_json["content"]
                # Decode the base64 encoded content
                decoded_content = base64.b64decode(content_data).decode("utf-8")
                file_contents.append(decoded_content)
                print(f"Content for {url}:")
                print(decoded_content)
            else:
                # Handle cases where "content" key is missing
                print(f"'content' key not found in the response for URL: {url}")
        else:
            # Log detailed error information for failed requests
            print(f"Failed to fetch {url}, Status Code: {response.status_code}")
            if response.text:
                print("Error details:", response.text)

    return file_contents


@app.route("/api/process-files", methods=["POST"])
def process_files():
    """Process the received files and modify content with OpenAI."""
    print("Received a request to /api/process-files")
    data = request.json
    file_urls = data.get("fileUrls", [])
    user_uid = data.get("userUid")

    if not file_urls or not user_uid:
        return jsonify({"error": "Missing data"}), 400

    try:
        token_doc = db.collection("access_tokens").document(user_uid).get()
        if token_doc.exists:
            github_token = token_doc.to_dict().get("githubAccessToken")
        else:
            return jsonify({"error": "Access token not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    file_contents = fetch_file_contents(github_token, file_urls)

    # Modify the content with OpenAI
    modified_contents = []
    for content in file_contents:
        modified_content = modify_content_with_openai(content)
        if modified_content:
            modified_contents.append(modified_content)
        else:
            # Handle the case where OpenAI modification fails
            modified_contents.append("Failed to modify content with OpenAI.")

    return (
        jsonify(
            {
                "message": "Files processed successfully",
                "fileContents": modified_contents,
            }
        ),
        200,
    )


def modify_content_with_openai(original_content):
    """Process content with OpenAI."""
    try:
        response = openai.Completion.create(
            model="text-davinci-003",  # Use the latest available model
            prompt=f"Add this text to the top of the following content - This content has been modified by AI!\n\n{original_content}",
            temperature=0.7,
            max_tokens=1024,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )
        modified_content = response.choices[0].text.strip()
        print("Modified Content:", modified_content)
        return modified_content
    except Exception as e:
        print("Error calling OpenAI:", e)
        return None


if __name__ == "__main__":
    app.run(debug=True)
