import os
import asyncio
from openai import AsyncAzureOpenAI

import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger
from chainlit.action import Action
from uuid import uuid4

from realtime import RealtimeClient
from realtime.tools import tools

client = AsyncAzureOpenAI(api_key=os.environ["AZURE_OPENAI_API_KEY"],
                          azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                          azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                          api_version="2024-10-01-preview")    

async def setup_openai_realtime(system_prompt: str):
    """Instantiate and configure the OpenAI Realtime Client"""
    openai_realtime = RealtimeClient(system_prompt = system_prompt)
    cl.user_session.set("track_id", str(uuid4()))
    
    async def handle_conversation_updated(event):
        item = event.get("item")
        delta = event.get("delta")
        """Currently used to stream audio back to the client."""
        if delta:
            # Only one of the following will be populated for any given event
            if 'audio' in delta:
                audio = delta['audio']  # Int16Array, audio added
                await cl.context.emitter.send_audio_chunk(cl.OutputAudioChunk(mimeType="pcm16", data=audio, track=cl.user_session.get("track_id")))
                
            if 'arguments' in delta:
                arguments = delta['arguments']  # string, function arguments added
                pass
            
    async def handle_item_completed(item):
        """Generate the transcript once an item is completed and populate the chat context."""
        try:
            transcript = item['item']['formatted']['transcript']
            if transcript != "":
                await cl.Message(content=transcript).send()
        except:
            pass
    
    async def handle_conversation_interrupt(event):
        """Used to cancel the client previous audio playback."""
        cl.user_session.set("track_id", str(uuid4()))
        await cl.context.emitter.send_audio_interrupt()
        
    async def handle_input_audio_transcription_completed(event):
        item = event.get("item")
        delta = event.get("delta")
        if 'transcript' in delta:
            transcript = delta['transcript']
            if transcript != "":
                msg = cl.Message(
                    author="You",
                    type="user_message",
                    content=transcript,
                    metadata={"type": "audio_transcript", "input_method": "voice"}
                )
                await msg.send()
                if transcript.strip().startswith("SYSTEM ORDER"):
                    await cl.Message(content="请使用文本输入来进行系统操作指令，语音仅支持普通问答。").send()
                else:
                    # 普通问答逻辑：把语音转文本内容发给 Realtime API
                    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
                    if openai_realtime and openai_realtime.is_connected():
                        await openai_realtime.send_user_message_content([
                            {"type": 'input_text', "text": transcript}
                        ])
        
    async def handle_error(event):
        logger.error(event)
        
    
    openai_realtime.on('conversation.updated', handle_conversation_updated)
    openai_realtime.on('conversation.item.completed', handle_item_completed)
    openai_realtime.on('conversation.interrupted', handle_conversation_interrupt)
    openai_realtime.on('conversation.item.input_audio_transcription.completed', handle_input_audio_transcription_completed)
    openai_realtime.on('error', handle_error)

    cl.user_session.set("openai_realtime", openai_realtime)
    coros = [openai_realtime.add_tool(tool_def, tool_handler) for tool_def, tool_handler in tools]
    await asyncio.gather(*coros)
    

system_prompt = '''You are the Deco Networking Assistant, responsible for providing proactive, intelligent, and friendly voice and text support throughout the user's Deco router setup journey. You must give precise, concise, and easy-to-understand answers and guidance based on the current page content and the user's voice/text input. 
You can only proceed to next steps in the Key Setup Steps if the user starts with "SYSTEM ORDER". Otherwise just general chat with the user.

# Interaction Principles
- Proactive Guidance: On every page switch or when the user clicks a key button, proactively use voice to explain the current step and suggest the next action, be gentle and patient.
- Real-time Response: The user can ask questions via voice or text at any time. You should answer professionally by combining the current page content, operational context, and local product documentation (RAG).
- Friendly Tone: Always maintain a patient, encouraging, and friendly tone to reduce user anxiety.
- Clear Steps: Only explain the key points of the current page and the next step each time to avoid information overload.
- Product Knowledge: If the user asks about product information, prioritize retrieving answers from local product documentation using RAG.

# Key Setup Steps
1. Welcome Page: Proactively say, "Let's start the setup journey. This will only take a few minutes. You can control me directly by talking to complete the setup, and feel free to ask me any questions at any time."
2. Check number of Deco devices: Ask user how many Deco devices he/she have. If the user has multiple Deco devices, start setup with the 1st device, after the 1st is setup completely, trigger the setup for the others in order. If only one device is present, say "Great! Let's start setting up your Deco device."
3. Permission Request Page: Explain the need for Bluetooth, Wi-Fi, and local network permissions. If user says "I agree." or "I allow", move to next step. If user says "I don't agree" or "I refuse", say "You can still use the Deco app without these permissions, but some features may not work properly."
4. Device Discovery Page: Confirm the device is found.
5. Connect Modem Page: Remind the user to connect the network cable and restart the modem.
6. Device Placement Page: Guide the user to choose the device placement location.
7. Connection Type Configuration Page: If PPPoE is detected, prompt the user to enter their account and password. If it's dynamic IP, then user doesn't need to do anything specifically.
8. Wi-Fi Settings Page: Ask if the user wants to generate a strong Wi-Fi configuration. If yes, automatically fill in the recommended settings. And once user gave the name and password, say "Great! Your Wi-Fi settings are ready. You can change them later in the Deco app. And don't read aloud about user name and password."
9. Configuration Deployment Page: Tell the user to wait for a few dozen seconds and proactively answer common questions about signal optimization, etc.
10. Success Page: Congratulate the user on successful setup.
11. (Optional) Device Management Page: If the user has multiple Deco devices, guide them to set up the next device(s) by looping the steps from 3 to 10 until all the devices are set up completely. If the user has only one Deco device, say "Congratulations! Your Deco device is successfully set up. You can now enjoy a better network experience."

# Other Requirements
- The user may ask questions about the page or product at any time. You must answer intelligently based on the current page and local documentation. You can only proceed to next step if the user start with "SYSTEM ORDER". Otherwise just general chat with the user.
- If you cannot answer a question, politely suggest the user contact customer support.
- All user data must be kept strictly confidential.

# Important Notes
You can only proceed to next steps in the Key Setup Steps if the user starts with "SYSTEM ORDER". Otherwise just general chat with the user.

# Voice Input Restriction
- Any voice input (even if it starts with "SYSTEM ORDER") can only be used for general Q&A and must **never** trigger or advance any Key Setup Steps.
- Only text input that starts with "SYSTEM ORDER" is allowed to advance Key Setup Steps.
'''

@cl.on_chat_start
async def start():
    await cl.Message(
        content="Hi, Welcome to Deco AI. Press the 'microphone' button below to talk!"
    ).send()
    await setup_openai_realtime(system_prompt=system_prompt + "\n\n Customer ID: 12121")

def get_message_type(message):
    # 优先用 metadata.type，其次用 message.type
    msg_type = None
    if hasattr(message, "metadata") and message.metadata and "type" in message.metadata:
        msg_type = message.metadata["type"]
    else:
        msg_type = getattr(message, "type", None)
    print(f"[DEBUG] message type: {msg_type}, message: {message}")
    return msg_type


@cl.on_message
async def on_message(message: cl.Message):
    # Initialize the track_id for audio playback
    cl.user_session.set("track_id", str(uuid4()))
    await cl.context.emitter.send_audio_interrupt()
    msg_type = get_message_type(message)
    print(f"[DEBUG] message type: {msg_type}, message: {message}")
    print(f"[DEBUG] message.__dict__: {message.__dict__}")  # 打印所有属性，便于排查
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    await message.remove()
    input_method = None
    if hasattr(message, "metadata") and message.metadata:
        input_method = message.metadata.get("input_method")
    if openai_realtime and openai_realtime.is_connected():
        # 只允许文本输入（非语音转文本）且以 SYSTEM ORDER 开头才进入下一步
        if (
            message.content.strip().startswith("SYSTEM ORDER")
            # and (input_method == "voice" or input_method == "text")
        ):
            await openai_realtime.send_user_message_content([{ "type": 'input_text', "text": message.content }])
            print("[DEBUG] SYSTEM ORDER message received")
        else:
            print("[DEBUG] SYSTEM ORDER message NOT received")
    else:
        await cl.Message(content="Please activate voice mode before sending messages!").send()

@cl.on_audio_start
async def on_audio_start():
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        # TODO: might want to recreate items to restore context
        # openai_realtime.create_conversation_item(item)
        await openai_realtime.connect()
        logger.info("Connected to OpenAI realtime")
        # 主动发送一句欢迎语音
        await openai_realtime.send_user_message_content([{ "type": 'input_text', "text": "Now let's start configuring the journey, this will only take a few minutes. You can control me directly through conversation to complete the setup, and feel free to ask me any questions at any time."}])
        return True
    except Exception as e:
        await cl.ErrorMessage(content=f"Failed to connect to OpenAI realtime: {e}").send()
        return False

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime:            
        if openai_realtime.is_connected():
            await openai_realtime.append_input_audio(chunk.data)
        else:
            logger.info("RealtimeClient is not connected")

@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.disconnect()