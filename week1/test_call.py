import plivo
from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN

# Your ngrok URL
NGROK_URL = "https://tamala-dilapidated-yaretzi.ngrok-free.dev"

def make_test_call(your_phone_number):
    """
    Make a test call to your phone to test the IVR.
    your_phone_number should be in format: +91XXXXXXXXXX (with country code)
    """
    client = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)

    # Plivo trial accounts have a sandbox number for testing
    response = client.calls.create(
        from_="+14157778888",  # Plivo test number (will show as Unknown/Private)
        to_=your_phone_number,
        answer_url=f"{NGROK_URL}/voice/incoming",
        answer_method="POST"
    )

    print(f"Call initiated!")
    print(f"Call UUID: {response.request_uuid}")
    return response


if __name__ == "__main__":
    # Replace with YOUR phone number (with country code)
    YOUR_NUMBER = input("Enter your phone number (e.g., +919876543210): ")
    make_test_call(YOUR_NUMBER)
