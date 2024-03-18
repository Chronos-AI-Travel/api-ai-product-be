"""Backend of Chronos"""

import base64
from flask import Flask, request, jsonify
from flask_mail import Mail, Message
from flask_cors import CORS
import requests
from firebase_admin import credentials, firestore, initialize_app
from openai import OpenAI
import config

client = OpenAI(api_key=config.OPEN_AI_KEY)

app = Flask(__name__)
CORS(app)

# OpenAI key


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


@app.route("/provider_request_email", methods=["POST"])
def provider_request_email():
    """Send an email to Nick and Josh when provider request is filled in"""
    data = request.json
    msg = Message(
        "Contact Form Submission from Cronos",
        sender="joshsparkes6@gmail.com",
        recipients=["joshsparkes6@gmail.com", "nick_castrioty@hotmail.com"],
    )
    msg.body = f"""
    Name: {data.get('fullName')}
    Company: {data.get('companyName')}
    Email: {data.get('workEmail')}
    Website: {data.get('companyURL')}
    API Integration: {data.get('apiIntegration')}
    Requirements: {data.get('requirements')}
    API Documentation URL: {data.get('apiDocumentationURL')}
    """
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")
        return jsonify({"message": "Failed to send email", "error": str(e)}), 500

    return jsonify({"message": "Email sent successfully"}), 200

@app.route("/fetch_file_contents", methods=["POST"])
def fetch_file_contents():
    data = request.json
    file_urls = data.get("fileUrls", [])
    user_uid = data.get("userUid")

    if not file_urls or not user_uid:
        return jsonify({"error": "Missing data"}), 400

    # Fetch the GitHub access token from Firestore
    try:
        token_doc = db.collection("access_tokens").document(user_uid).get()
        if token_doc.exists:
            github_token = token_doc.to_dict().get("githubAccessToken")
            if not github_token:
                return jsonify({"error": "GitHub token not found"}), 404
        else:
            return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": "Failed to fetch user data", "details": str(e)}), 500

    # Use the fetched GitHub token to retrieve file contents
    headers = {"Authorization": f"token {github_token}"}
    file_contents = []

    for url in file_urls:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            response_json = response.json()
            if "content" in response_json:
                content_data = response_json["content"]
                decoded_content = base64.b64decode(content_data).decode("utf-8")
                file_contents.append({"url": url, "content": decoded_content})
            else:
                print(f"'content' key not found in the response for URL: {url}")
        else:
            print(f"Failed to fetch {url}, Status Code: {response.status_code}")
            if response.text:
                print("Error details:", response.text)

    # Return the list of file contents as a JSON response
    return jsonify(file_contents)


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
                "modifiedContents": modified_contents,
            }
        ),
        200,
    )


def modify_content_with_openai(original_content):
    """Process content with OpenAI."""
    prompt = f"Adjust the following content so that in your response it says 'This content has been updated by AI' then follow with the content:\n\n{original_content}"
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        if response.choices:
            modified_content = response.choices[0].message.content
            return modified_content
        else:
            return "Modification failed."
    except Exception as e:
        print(f"Error calling OpenAI: {e}")
        return "Failed to modify content with OpenAI."


@app.route("/api/create-branch-and-commit", methods=["POST"])
def create_branch_and_commit():
    """Creating a new branch with updated content"""
    data = request.json
    user_uid = data.get("userUid")
    branch_name = data.get("branchName")
    file_contents = data.get("fileContents")
    file_path = data.get("filePath")

    # Steps:
    # 1. Authenticate with GitHub using the user's access token.
    # 2. Get the latest commit SHA of the base branch (e.g., main).
    # 3. Create a new branch with the given name.
    # 4. Create or update the file in the new branch with the modified contents.

    # This is a complex operation that involves multiple GitHub API requests.
    # You'll need to implement the logic for each step, handling authentication,
    # error checking, and the specific GitHub API requests.

    return jsonify({"message": "Branch and file created successfully"}), 200


@app.route("/api/query-agent", methods=["POST"])
def query_agent():
    """agent communication endpoint"""
    user_input = request.json.get("input")
    # URL of your locally running AutoGPT agent
    agent_url = "http://localhost:8000"

    # Assuming the agent expects a POST request with 'input' in the JSON body
    # Adjust this based on your agent's API
    response = requests.post(agent_url, json={"input": user_input})
    if response.status_code == 200:
        # Forward the agent's response back to the frontend
        return jsonify(response.json())
    else:
        return (
            jsonify({"error": "Failed to get response from the agent"}),
            response.status_code,
        )


if __name__ == "__main__":
    app.run(debug=True)
