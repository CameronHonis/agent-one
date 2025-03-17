import socket
import pyaudio
import argparse
import ast


class AudioClient:
    def __init__(self, server_host="localhost", server_port=9999):
        self.server_host = server_host
        self.server_port = server_port
        self.running = False
        self.socket = None
        self.audio = None
        self.stream = None

    def connect(self):
        try:
            # Create socket and connect to server
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            print(f"Connected to server at {self.server_host}:{self.server_port}")

            # Receive audio parameters
            params_data = self.socket.recv(1024).decode()
            self.params = ast.literal_eval(params_data)
            print(f"Audio parameters: {self.params}")

            # Send acknowledgment
            self.socket.sendall(b"OK")

            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=self.audio.get_format_from_width(self.params["sample_width"]),
                channels=self.params["channels"],
                rate=self.params["framerate"],
                output=True,
            )

            return True
        except Exception as e:
            print(f"Connection error: {e}")
            self.cleanup()
            return False

    def start_playback(self):
        if not self.socket or not self.stream:
            print("Not connected. Call connect() first.")
            return False

        self.running = True
        print("Starting audio playback...")

        try:
            while self.running:
                # Receive data size
                size_bytes = self.socket.recv(4)
                if not size_bytes:
                    break

                size = int.from_bytes(size_bytes, byteorder="big")

                # Receive audio data
                data = b""
                while len(data) < size:
                    chunk = self.socket.recv(size - len(data))
                    if not chunk:
                        break
                    data += chunk

                if len(data) == size:
                    # Play audio
                    self.stream.write(data)
                else:
                    # Connection lost
                    break

        except Exception as e:
            print(f"Playback error: {e}")
        finally:
            self.stop()

        return True

    def stop(self):
        self.running = False
        self.cleanup()

    def cleanup(self):
        # Close audio stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            self.stream = None

        # Close PyAudio
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
            self.audio = None

        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        print("Client stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Streaming Client")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=9999, help="Server port")
    args = parser.parse_args()

    client = AudioClient(args.host, args.port)

    try:
        if client.connect():
            client.start_playback()
    except KeyboardInterrupt:
        print("\nStopping client...")
    finally:
        client.stop()
