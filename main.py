import os
import time
import re
from pydantic import BaseModel
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
# pyrefly: ignore [missing-import]
from google.oauth2.credentials import Credentials
# pyrefly: ignore [missing-import]
from googleapiclient.discovery import build
# pyrefly: ignore [missing-import]
from typesafe_sdk import TypeSafeClient, Noul, Choice
# Load variables from the .env file into the environment
load_dotenv()
app = FastAPI()
client = TypeSafeClient(api_key=os.getenv("API_KEY"))

class EmailProcessRequest(BaseModel):
    # Pass stored user credentials or token scopes securely from your frontend/environment
    user_email: str

@app.post("/scan-expenses")
def scan_bank_emails(payload: EmailProcessRequest):
    try:
        # Step 1: Connect to Gmail API (Assumes standard OAuth token configuration)
        # Note: In production, securely load user-specific credentials.
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.readonly'])
        service = build('gmail', 'v1', credentials=creds)

        # Step 2: Query last 500 messages from senders containing "bank"
        query = "from:bank"
        results = service.users().messages().list(userId='me', q=query, maxResults=100).execute()
        messages = results.get('messages', [],)

        extracted_expenses = []

        for msg_info in messages:
            msg = service.users().messages().get(userId='me', id=msg_info['id'], format='full').execute()
            
            # Extract email body snippet/payload text
            payload_data = msg.get('payload', {})
            headers = payload_data.get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            snippet = msg.get('snippet', '')
            
            # Combine subject and snippet/body for context state
            email_state = f"Subject: {subject}\nBody: {snippet}"

            # Step 3: Use Jev to classify and decide if it's a valid financial transaction
            jev_response = client.system_one(
                state=email_state,
                questions={
                    "is_transaction": Noul(instructions="Does this email describe a successful money debit, purchase, or bill payment?"),
                    "is_cc_transaction": Noul(instructions="Does this email describe a successful money debit, purchase, or bill payment for credit card?"),
                    "category": Choice(
                        instructions="What expense category best fits this transaction?",
                        criteria={
                            "Food": "Restaurant, food delivery, or grocery payments", 
                            "Transport": "Cabs, fuel, flights, or transit passes", 
                            "Shopping": "E-commerce or retail store purchases", 
                            "Bills": "Utilities, subscriptions, or credit card bills", 
                            "Other": "Everything else"
                        }
                    )
                }
            )

            # Check Jev's calibrated confidence probability for transaction match
            is_txn_prob = jev_response.nouls["is_transaction"].noul
            if is_txn_prob > 0.85: # High confidence filter
                chosen_category = jev_response.choices["category"].choice
                is_credit_card = jev_response.nouls["is_cc_transaction"].noul > 0.5
                # Extract amount locally using safe regex from the snippet/subject
                amount_match = re.search(r'(?:INR|Rs\.?|₹|\$)\s*([\d,]+\.?\d*)', email_state)
                extracted_amount = amount_match.group(1) if amount_match else "Unknown"
                extracted_expenses.append({
                    "id": msg_info['id'],
                    "subject": subject,
                    "snippet": snippet,
                    "category": chosen_category,
                    "credit_card_transaction": is_credit_card,
                    "amount": extracted_amount,
                    "confidence": is_txn_prob
                })
            time.sleep(0.2)
        return {"status": "success", "count": len(extracted_expenses), "expenses": extracted_expenses}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))