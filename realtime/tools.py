import json
import random
import chainlit as cl
from datetime import datetime, timedelta

# Function Definitions

schedule_callback_def = {  
    "name": "schedule_callback",  
    "description": "Schedule a callback with a customer service representative",  
    "parameters": {  
        "type": "object",  
        "properties": {  
            "customer_id": {
                "type": "string",
                "description": "The unique identifier for the customer"
            },
            "callback_time": {  
                "type": "string",  
                "description": "Preferred time for the callback in ISO 8601 format"  
            }  
        },  
        "required": ["customer_id", "callback_time"]  
    }  
}  

  

async def schedule_callback_handler(customer_id, callback_time):  
        # Read the HTML template
    with open('callback_schedule_template.html', 'r') as file:
        html_content = file.read()

    # Replace placeholders with actual data
    html_content = html_content.format(
        customer_id=customer_id,
        callback_time=callback_time
    )

    # Return the Chainlit message with HTML content
    await cl.Message(content=f"Your callback has been scheduled. Here are the details:\n{html_content}").send()
    return f"Callback scheduled for customer {customer_id} at {callback_time}. A representative will contact you then."
  

# Tools list
tools = [
    (schedule_callback_def, schedule_callback_handler),      
]