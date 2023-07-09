from fastapi import FastAPI, Request, Response
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from pydantic import BaseModel
import os
import requests
import json
from google.cloud import secretmanager
from dotenv import main
from nltk.tokenize import word_tokenize
import re
import nltk
if not nltk.data.find('tokenizers/punkt'):
    nltk.download('punkt')



# Initialize the FastAPI app
app = FastAPI()

# Secret Management

from google.cloud import secretmanager

def access_secret_version(project_id, secret_id, version_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode('UTF-8')

env_vars = {
    'SLACK_BOT_TOKEN': access_secret_version('slack-bot-391618', 'SLACK_BOT_TOKEN', 'latest'),
    'SLACK_SIGNING_SECRET': access_secret_version('slack-bot-391618', 'SLACK_SIGNING_SECRET', 'latest'),
}

os.environ.update(env_vars)

ETHEREUM_ADDRESS_PATTERN = r'\b0x[a-fA-F0-9]{40}\b'
BITCOIN_ADDRESS_PATTERN = r'\b(1|3)[1-9A-HJ-NP-Za-km-z]{25,34}\b|bc1[a-zA-Z0-9]{25,90}\b'
LITECOIN_ADDRESS_PATTERN = r'\b(L|M)[a-km-zA-HJ-NP-Z1-9]{26,34}\b'
DOGECOIN_ADDRESS_PATTERN = r'\bD{1}[5-9A-HJ-NP-U]{1}[1-9A-HJ-NP-Za-km-z]{32}\b'
XRP_ADDRESS_PATTERN = r'\br[a-zA-Z0-9]{24,34}\b'

# BIP39 Filter

def contains_bip39_phrase(message):
    words = word_tokenize(message.lower())
    bip39_words = [word for word in words if word in BIP39_WORDS]
    return len(bip39_words) >= 23

with open('bip39_words.txt', 'r') as file:
    BIP39_WORDS = set(word.strip() for word in file)

# Initialize the Slack client
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# Initialize the Slack Signature Verifier
signature_verifier = SignatureVerifier(os.getenv("SLACK_SIGNING_SECRET"))

# Initialize bot user_id
bot_id = slack_client.auth_test()['user_id'] #new

# Track event IDs to ignore duplicates
processed_event_ids = set()

class SlackEvent(BaseModel):
    type: str
    user: str
    text: str
    channel: str

def react_description(query):
    response = requests.post('http://', json={"user_input": query})
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
        if re.search(ETHEREUM_ADDRESS_PATTERN, user_text, re.IGNORECASE) or \
           re.search(BITCOIN_ADDRESS_PATTERN, user_text, re.IGNORECASE) or \
           re.search(LITECOIN_ADDRESS_PATTERN, user_text, re.IGNORECASE) or \
           re.search(DOGECOIN_ADDRESS_PATTERN, user_text, re.IGNORECASE) or \
           re.search(XRP_ADDRESS_PATTERN, user_text, re.IGNORECASE):
            response_text = "I'm sorry, but I can't assist with questions that include cryptocurrency addresses. Please remove the address and ask again."
        elif contains_bip39_phrase(user_text):
            response_text = "It looks like you've included a recovery phrase in your message. Please never share your recovery phrase. It is the master key to your wallet and should be kept private."
        else:
            # Event handler
            response_text = react_description(user_text)
        user_id = event.get('user') #new
            #response_text = react_description(user_text, user_id) #new
        response_text = f'<@{user_id}> {response_text}'

        # Send a response back to Slack in the thread where the bot was mentioned
        slack_client.chat_postMessage(
            channel=event.get('channel'),
            text=response_text,
            thread_ts=event.get('ts')  
        )

    return Response(status_code=200)

#####RUN COMMAND########
#  uvicorn slack_bot:app --port 8000


#####RUN COMMADND########
#  uvicorn slack_bot:app --port 8000
# in Google Cloud 
# sudo uvicorn slack_bot:app --port 80 --host 0.0.0.0

########VM Service Commands#####

# sudo nano /etc/nginx/sites-available/myproject
# sudo systemctl restart nginx
#sudo systemctl stop nginx

# sudo nano /etc/systemd/system/slack_bot.service
# sudo systemctl daemon-reload
# sudo systemctl start slack_bot to start the service.
# sudo systemctl stop slack_bot to stop the service.
# sudo systemctl restart slack_bot to restart the service (after modifying the code for example)
# sudo systemctl status slack_bot to check the status of the service.
# journalctl -u slack_bot.service -e to check logs
