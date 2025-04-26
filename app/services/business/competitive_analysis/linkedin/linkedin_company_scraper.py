from apify_client import ApifyClient
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize the ApifyClient with your API token
client = ApifyClient(os.getenv("APIFY_API_KEY"))

# Prepare the Actor input
run_input = {
    "action": "get-companies",
    "isName": True,
    "isUrl": False,
    "keywords": [
        "Fincaraíz"
    ],
    "location": [
        "Colombia"
    ]
}

# Run the Actor and wait for it to finish
run = client.actor("od6RadQV98FOARtrp").call(run_input=run_input)

# Fetch and print Actor results from the run's dataset (if there are any)
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item)