import plivo
from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN


def get_client():
    """Create and return a Plivo client."""
    return plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)


def check_account_details(client):
    """Check account details and balance."""
    print("\n--- Account Details ---")
    try:
        account = client.account.get()
        print(f"Account Name: {account.name}")
        print(f"Account Type: {account.account_type}")
        print(f"Cash Credits: ${account.cash_credits}")
        print(f"Timezone: {account.timezone}")
        return True
    except Exception as e:
        print(f"Error fetching account: {e}")
        return False


def check_phone_numbers(client):
    """Check owned phone numbers."""
    print("\n--- Phone Numbers ---")
    try:
        numbers = client.numbers.list()
        if numbers:
            for number in numbers:
                print(f"  {number.number} ({number.region})")
        else:
            print("  No phone numbers found. You can rent one from the Plivo console.")
        return True
    except Exception as e:
        print(f"Error fetching numbers: {e}")
        return False


def check_applications(client):
    """Check configured applications."""
    print("\n--- Applications ---")
    try:
        apps = client.applications.list()
        if apps:
            for app in apps:
                print(f"  {app.app_name} (ID: {app.app_id})")
        else:
            print("  No applications configured yet.")
        return True
    except Exception as e:
        print(f"Error fetching applications: {e}")
        return False


def check_message_logs(client):
    """Check recent message logs."""
    print("\n--- Recent Messages ---")
    try:
        # Get messages from the last 24 hours
        from datetime import datetime, timedelta

        messages = client.messages.list(limit=10)

        if not messages:
            print("  No messages found")
            return True

        sent_today = 0
        failed_count = 0

        for msg in messages:
            status = getattr(msg, 'message_state', 'unknown')
            direction = getattr(msg, 'message_direction', 'unknown')
            to_number = getattr(msg, 'to_number', 'unknown')

            # Count stats
            if status in ['failed', 'undelivered']:
                failed_count += 1
                print(f"  FAILED: to {to_number} - {status}")
            else:
                sent_today += 1
                print(f"  {direction}: to {to_number} - {status}")

        print(f"\n  Summary: {sent_today} delivered, {failed_count} failed")
        return True

    except Exception as e:
        print(f"Error fetching messages: {e}")
        return False


def check_call_logs(client):
    """Check recent call logs."""
    print("\n--- Recent Calls ---")
    try:
        calls = client.calls.list(limit=10)

        if not calls:
            print("  No calls found")
            return True

        for call in calls:
            direction = getattr(call, 'call_direction', 'unknown')
            from_num = getattr(call, 'from_number', 'unknown')
            to_num = getattr(call, 'to_number', 'unknown')
            status = getattr(call, 'end_reason', 'unknown')
            duration = getattr(call, 'bill_duration', 0)

            print(f"  {direction}: {from_num} -> {to_num} ({duration}s) - {status}")

        return True

    except Exception as e:
        print(f"Error fetching calls: {e}")
        return False


def run_health_check():
    """Run all health checks."""
    print("=" * 40)
    print("PLIVO ACCOUNT HEALTH CHECK")
    print("=" * 40)

    if not PLIVO_AUTH_ID or not PLIVO_AUTH_TOKEN:
        print("\nError: Missing credentials!")
        print("Please add your PLIVO_AUTH_ID and PLIVO_AUTH_TOKEN to the .env file")
        return False

    client = get_client()

    results = []
    results.append(("Account Details", check_account_details(client)))
    results.append(("Phone Numbers", check_phone_numbers(client)))
    results.append(("Applications", check_applications(client)))
    results.append(("Message Logs", check_message_logs(client)))
    results.append(("Call Logs", check_call_logs(client)))

    print("\n" + "=" * 40)
    print("SUMMARY")
    print("=" * 40)

    all_passed = True
    for name, passed in results:
        status = "✓ OK" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    return all_passed


if __name__ == "__main__":
    success = run_health_check()
    print("\n" + "=" * 40)
    if success:
        print("All checks passed!")
    else:
        print("Some checks failed. Review above.")
    print("=" * 40)
