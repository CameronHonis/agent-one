import React from "react"

function App() {
    React.useEffect(() => {
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            console.log(`You said: ${transcript}`);
        };

        recognition.start();
    });
}

export default App
