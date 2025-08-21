import asyncio
import logging
import websockets
from typing import Callable, Any

class GenericWebSocketClient:
    """
    A generic client for connecting to a WebSocket and processing messages.
    """
    def __init__(self, uri: str, message_handler: Callable[[Any], None]):
        """
        Initializes the client.

        :param uri: The WebSocket URI to connect to.
        :param message_handler: A callback function to be called for each message received.
        """
        self.uri = uri
        self.message_handler = message_handler
        self.is_running = False

    async def run(self):
        """
        Connects to the WebSocket and runs the message listening loop.
        """
        self.is_running = True
        logging.info(f"Connecting to WebSocket: {self.uri}")
        try:
            async with websockets.connect(self.uri) as websocket:
                logging.info(f"Successfully connected to {self.uri}")
                while self.is_running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        self.message_handler(message)
                    except asyncio.TimeoutError:
                        logging.debug(f"No message received in 30s, sending ping.")
                        # Send a ping to keep the connection alive
                        await websocket.ping()
                    except websockets.exceptions.ConnectionClosed:
                        logging.warning("WebSocket connection closed. Attempting to reconnect...")
                        break # Exit the inner loop to trigger reconnection
        except Exception as e:
            logging.error(f"Error in WebSocket client: {e}")

        if self.is_running:
            await asyncio.sleep(5) # Wait before reconnecting
            await self.run() # Reconnect

    def stop(self):
        """
        Stops the client.
        """
        self.is_running = False
        logging.info("WebSocket client stopping.")
