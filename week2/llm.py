"""
Week 2, Day 1: LLM APIs
- Basic chat completion
- Streaming responses
- Function calling
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ============ 1. Basic Chat Completion ============

def chat(message, system_prompt="You are a helpful assistant."):
    """
    Simple chat completion - send a message, get a response.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Fast and cheap model
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content


# ============ 2. Streaming Responses ============

def chat_stream(message, system_prompt="You are a helpful assistant."):
    """
    Streaming chat - get response word by word (better for real-time).
    Yields chunks as they arrive.
    """
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        stream=True  # Enable streaming
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ============ 3. Function Calling ============

# Define tools (functions) the AI can call
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name, e.g., 'Mumbai' or 'New York'"
                    }
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_appointment",
            "description": "Schedule an appointment with the sales or support team",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "enum": ["sales", "support"],
                        "description": "Which department to schedule with"
                    },
                    "date": {
                        "type": "string",
                        "description": "Preferred date, e.g., 'tomorrow' or '2024-02-10'"
                    },
                    "time": {
                        "type": "string",
                        "description": "Preferred time, e.g., '2pm' or '14:00'"
                    }
                },
                "required": ["department", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up an order by order ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to look up"
                    }
                },
                "required": ["order_id"]
            }
        }
    }
]


# Mock function implementations (in real app, these would call actual APIs)
def get_weather(location):
    """Mock weather function."""
    return {"location": location, "temperature": "28°C", "condition": "Sunny"}


def schedule_appointment(department, date, time=None):
    """Mock scheduling function."""
    return {
        "status": "confirmed",
        "department": department,
        "date": date,
        "time": time or "10:00 AM",
        "confirmation_id": "APT-12345"
    }


def lookup_order(order_id):
    """Mock order lookup function."""
    return {
        "order_id": order_id,
        "status": "shipped",
        "estimated_delivery": "Feb 8, 2026"
    }


# Function dispatcher
FUNCTION_MAP = {
    "get_weather": get_weather,
    "schedule_appointment": schedule_appointment,
    "lookup_order": lookup_order
}


def chat_with_functions(message, system_prompt="You are a helpful IVR assistant for a company."):
    """
    Chat with function calling - AI can use tools to get information.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]

    # First API call - AI decides if it needs to call a function
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"  # Let AI decide when to use tools
    )

    assistant_message = response.choices[0].message

    # Check if AI wants to call a function
    if assistant_message.tool_calls:
        # Add assistant's response to messages
        messages.append(assistant_message)

        # Process each function call
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            print(f"  → Calling function: {function_name}({function_args})")

            # Execute the function
            if function_name in FUNCTION_MAP:
                result = FUNCTION_MAP[function_name](**function_args)
            else:
                result = {"error": "Function not found"}

            # Add function result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })

        # Second API call - AI generates final response with function results
        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        return final_response.choices[0].message.content

    # No function call needed, return direct response
    return assistant_message.content


# ============ Demo Functions ============

def demo_basic():
    """Demo basic chat completion."""
    print("\n" + "="*50)
    print("DEMO 1: Basic Chat")
    print("="*50)

    response = chat("What is an IVR system in 2 sentences?")
    print(f"\nQ: What is an IVR system?")
    print(f"A: {response}")


def demo_streaming():
    """Demo streaming responses."""
    print("\n" + "="*50)
    print("DEMO 2: Streaming Response")
    print("="*50)

    print("\nQ: Explain how voice AI works in 3 sentences.")
    print("A: ", end="", flush=True)

    for chunk in chat_stream("Explain how voice AI works in 3 sentences."):
        print(chunk, end="", flush=True)

    print("\n")


def demo_functions():
    """Demo function calling."""
    print("\n" + "="*50)
    print("DEMO 3: Function Calling")
    print("="*50)

    queries = [
        "What's the weather in Mumbai?",
        "I'd like to schedule a meeting with sales for tomorrow at 3pm",
        "Can you check the status of order ORD-789?"
    ]

    for query in queries:
        print(f"\nQ: {query}")
        response = chat_with_functions(query)
        print(f"A: {response}")


if __name__ == "__main__":
    print("🤖 Week 2, Day 1: LLM APIs Demo")
    print("================================")

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ Error: OPENAI_API_KEY not found in .env file")
        print("Add this line to your .env file:")
        print("OPENAI_API_KEY=your_api_key_here")
        exit(1)

    print("✓ OpenAI API key found")

    # Run demos
    demo_basic()
    demo_streaming()
    demo_functions()

    print("\n" + "="*50)
    print("✅ All demos complete!")
    print("="*50)
