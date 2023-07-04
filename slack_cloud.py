from fastapi import FastAPI, Request, Response
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from pydantic import BaseModel
import os
import requests
import json
import re  

from dotenv import main
main.load_dotenv() 

# Initialize the FastAPI app
app = FastAPI()

#Initialize .env variables
SLACK_BOT_TOKEN= os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET= os.getenv("SLACK_SIGNING_SECRET")

# Define Ethereum and Bitcoin address regex patterns
ETHEREUM_ADDRESS_PATTERN = r'\b0x[a-fA-F0-9]{40}\b'
BITCOIN_ADDRESS_PATTERN = r'\b(1|3)[1-9A-HJ-NP-Za-km-z]{25,34}\b|bc1[a-zA-Z0-9]{25,90}\b'


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

        user_text = event.get('text')
        # Check for cryptocurrency addresses in the user's text
        if re.search(ETHEREUM_ADDRESS_PATTERN, user_text, re.IGNORECASE) or re.search(BITCOIN_ADDRESS_PATTERN, user_text, re.IGNORECASE):
            response_text = "I'm sorry, but I can't assist with questions that include Ethereum or Bitcoin addresses. Please remove the address and ask again."
        else:
            # Event handler
            response_text = react_description(user_text)

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
