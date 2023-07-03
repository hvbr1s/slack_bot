from fastapi import FastAPI, Request, Response
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from pydantic import BaseModel
import os
import requests
import json
from google.cloud import secretmanager
from dotenv import main

main.load_dotenv() 

# Initialize the FastAPI app
app = FastAPI()

def access_secret_version(project_id, secret_id, version_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')

env_vars = {
    'SLACK_BOT_TOKEN': access_secret_version('your-gcp-project-id', 'SLACK_BOT_TOKEN', 'latest'),
    'SLACK_SIGNING_SECRET': access_secret_version('your-gcp-project-id', 'ALCHEMY_API_KEY', 'latest'),
}

os.environ.update(env_vars)

# Initialize the Slack client
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# Initialize the Slack Signature Verifier
signature_verifier = SignatureVerifier(os.getenv("SLACK_SIGNING_SECRET"))

# Initialize bot user_id
bot_id = slack_client.auth_test()['user_id']

# Track event IDs to ignore duplicates
processed_event_ids = set()


class SlackEvent(BaseModel):
    type: str
    user: str
    text: str
    channel: str

def react_description(query):
    response = requests.post('http://127.0.0.1:8008/gpt', json={"user_input": query})
    return response.json()['output']

@app.post("/")
async def slack_events(request: Request):
    # Get the request body
    body_bytes = await request.body()
    body = json.loads(body_bytes)

    # Verify the request from Slack
    if not signature_verifier.is_valid_request(body_bytes, request.headers):
        return Response(status_code=403)

    # Check if this is a URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}

    # Parse the event
    event = body.get('event')

    # Ignore duplicate events
    event_id = event.get('event_ts')
    if event_id in processed_event_ids:
        return Response(status_code=200)
    processed_event_ids.add(event_id)

    if event and event.get('type') == "app_mention":
        # Check if the message event is from the bot itself
        if event.get('user') == bot_id:
            return Response(status_code=200)

        # This is where you would handle the event
        # For example, if you receive a message event, you could send it to your GPT model
        response_text = react_description(event.get('text'))

        # Add the user's mention to the response
        user_id = event.get('user')
        response_text = f'<@{user_id}> {response_text}'

        # Send a response back to Slack in the thread where the bot was mentioned
        slack_client.chat_postMessage(
            channel=event.get('channel'),
            text=response_text,
            thread_ts=event.get('ts')  
        )

    return Response(status_code=200)



#####RUN COMMADND########
#  uvicorn slack_bot:app --port 8000
# in Google Cloud 
# sudo uvicorn api_bot:app --port 80 --host 0.0.0.0
