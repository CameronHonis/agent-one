import React from "react"

function App() {
    React.useEffect(() => {
        // Set up SSE connection for server-to-client messages
        const eventSource = new EventSource('http://localhost:8080/api/events/1');

        // Listen for server requests
        eventSource.addEventListener('message', async (event) => {
            const request = JSON.parse(event.data);

            if (request.type === 'screenCapture') {
                // Capture screen and send back
                console.log("requesting screen access placeholder");
                // Send response back to server
                await fetch('/api/response', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: request.id, data: "screen data placeholder" })
                });
            }
        });
    });
}

export default App
