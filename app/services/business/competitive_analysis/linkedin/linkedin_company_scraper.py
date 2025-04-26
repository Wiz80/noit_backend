from apify_client import ApifyClient
from dotenv import load_dotenv
import os
import json

load_dotenv()

# Initialize the ApifyClient with your API token
client = ApifyClient(os.getenv("APIFY_API_KEY"))

# Prepare the Actor input for URL-based company search
run_input = {
    "action": "get-companies",
    "isName": True,
    "isUrl": False,
    "keywords": [],
    "urls": [
        "udemy"
    ],
    "limit": 10
}

print(f"Using run input: {json.dumps(run_input, indent=2)}")

# Run the Actor and wait for it to finish
run = client.actor("od6RadQV98FOARtrp").call(run_input=run_input)

# Fetch and print Actor results from the run's dataset (if there are any)
results = []
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    results.append(item)
    print(item)

print(f"Found {len(results)} results")