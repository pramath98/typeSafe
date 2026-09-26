import os
# pyrefly: ignore [missing-import]
from google_auth_oauthlib.flow import InstalledAppFlow

# The Gmail read-only scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def main():
    # Make sure you have downloaded your OAuth client secrets file from Google Cloud Console 
    # and renamed/saved it as 'credentials.json' in this same folder.
    if not os.path.exists('credentials.json'):
        print("Error: 'credentials.json' not found. Download it from Google Cloud Console.")
        return

    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)

    # Save the credentials to token.json for future API calls
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    
    print("Success! 'token.json' has been generated.")

if __name__ == '__main__':
    main()