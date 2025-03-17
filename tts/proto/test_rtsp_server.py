import socket
import threading
import wave
import time
import argparse
import os

class AudioServer:
    def __init__(self, audio_file, host='0.0.0.0', port=9999):
        self.audio_file = audio_file
        self.host = host
        self.port = port
        self.chunk_size = 1024
        self.clients = []
        self.running = False
        
    def start(self):
        # Open wave file
        try:
            self.wave_file = wave.open(self.audio_file, 'rb')
            print(f"Audio file info: {self.wave_file.getframerate()}Hz, {self.wave_file.getnchannels()} channels")
        except Exception as e:
            print(f"Error opening audio file: {e}")
            return False
            
        # Create server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Error starting server: {e}")
            return False
            
        self.running = True
        
        # Start threads
        threading.Thread(target=self.accept_clients).start()
        threading.Thread(target=self.stream_audio).start()
        
        return True
        
    def accept_clients(self):
        print("Waiting for clients...")
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"New client connected: {addr}")
                
                # Send audio parameters to client
                params = {
                    'channels': self.wave_file.getnchannels(),
                    'sample_width': self.wave_file.getsampwidth(),
                    'framerate': self.wave_file.getframerate(),
                    'chunk_size': self.chunk_size
                }
                client.sendall(str(params).encode())
                
                # Wait for acknowledgment
                client.recv(1024)
                
                self.clients.append(client)
            except Exception as e:
                if self.running:
                    print(f"Error accepting client: {e}")
                break
                
    def stream_audio(self):
        print("Starting audio stream...")
        try:
            while self.running:
                # Read chunk from wave file
                data = self.wave_file.readframes(self.chunk_size)
                if not data:
                    # Loop the audio
                    self.wave_file.rewind()
                    data = self.wave_file.readframes(self.chunk_size)
                
                # Send to all clients
                clients_to_remove = []
                for client in self.clients:
                    try:
                        # Send the size of data first
                        size = len(data)
                        client.sendall(size.to_bytes(4, byteorder='big'))
                        
                        # Then send the data
                        client.sendall(data)
                    except:
                        clients_to_remove.append(client)
                
                # Remove disconnected clients
                for client in clients_to_remove:
                    print("Client disconnected")
                    self.clients.remove(client)
                    try:
                        client.close()
                    except:
                        pass
                
                # Control streaming speed based on audio parameters
                time.sleep(self.chunk_size / self.wave_file.getframerate() / 2)
        except Exception as e:
            print(f"Error streaming audio: {e}")
        
    def stop(self):
        self.running = False
        
        # Close client connections
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        
        # Close server socket
        try:
            self.server_socket.close()
        except:
            pass
            
        # Close wave file
        try:
            self.wave_file.close()
        except:
            pass
            
        print("Server stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Streaming Server")
    parser.add_argument("--file", required=True, help="Path to WAV audio file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=9999, help="Port to use")
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"Error: Audio file {args.file} not found")
        exit(1)
    
    server = AudioServer(args.file, args.host, args.port)
    
    try:
        if server.start():
            print("Server running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.stop()