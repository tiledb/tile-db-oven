
const prefix = "{{ prefix }}"; // Jinja variable passed from Flask

let serConnected = false;
let consoleBuffer = [];

// DOM elements
const connectBtn = document.getElementById("connectBtn");
const disconnectBtn = document.getElementById("disconnectBtn");
const sendBtn = document.getElementById("sendBtn");
const portSelect = document.getElementById("port");
const baudInput = document.getElementById("baudrate");
const manualCmd = document.getElementById("manualCmd");
const connectLabel = document.getElementById("connectLabel");
const connectionLed = document.getElementById("connectionLed");
const receiveLed = document.getElementById("receiveLed");
const consoleOutput = document.getElementById("consoleOutput");

// --- Helper: Append line to console with auto-scroll ---
const appendConsoleLine = (line) => {
    const div = document.createElement("div");
    div.textContent = line;
    div.classList.add("console-line");
    consoleOutput.appendChild(div);

    // Keep last 500 lines
    while (consoleOutput.children.length > 500) {
        consoleOutput.removeChild(consoleOutput.firstChild);
    }

    // Scroll the container to bottom reliably
    const container = consoleOutput.parentElement; // .console-box
    container.scrollTop = container.scrollHeight;
};

// --- Connect ---
connectBtn.addEventListener("click", async () => {
    if (!serConnected) {
        const port = portSelect.value;
        const baudrate = baudInput.value;
        try {
          
            const res = await fetch(`${window.APP_PREFIX}/connect`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ port, baudrate })
            });
            const data = await res.json();
            if (data.status === "connected") {
                serConnected = true;
                connectLabel.textContent = "Connected";
                connectionLed.classList.add("green");
                connectionLed.classList.remove("red");
                appendConsoleLine("------connected-------");
            } else {
                alert("Error connecting: " + data.msg);
            }
        } catch (e) {
            alert("Error connecting serial: " + e);
        }
    }
});

// --- Disconnect ---
disconnectBtn.addEventListener("click", async () => {
    try {
        const res = await fetch(`${window.APP_PREFIX}/disconnect`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await res.json();
        if (data.status === "disconnected") {
            serConnected = false;
            connectBtn.textContent = "Connect";
            connectLabel.textContent = "Disconnected";
            connectionLed.classList.remove("green","blink");
            connectionLed.classList.add("red");  
            receiveLed.classList.remove("green","blink");
            appendConsoleLine("------disconnected-------");

            // Refresh page
            setTimeout(() => {
                location.reload(); // like pressing F5
            }, 200); // small delay so the last line is shown
        } else {
            alert("Error disconnecting: " + data.msg);
        }
    } catch (e) {
        console.error(e);
        alert("Error disconnecting serial");
    }
});



// Set help text
const manualHelpText = `
Commands are "A,B" where:
A = register/address, B = value
0: idle/run (0=idle,1=run)
1: set min temperature (°C)
2: set max temperature (°C)
3: heater (0=off,1=on)
4: power (0=off,1=on)
5-8: DB LV supply 0-3 (0=off,1=on)
9: run hours
10: run minutes
11: print settings
13: read voltages
14: read oven temp
15: debug mode (0=off,1=on)
`;
document.getElementById("manualHelpText").textContent = manualHelpText;

// Show overlay on click
document.getElementById("manualHelp").addEventListener("click", () => {
    document.getElementById("manualHelpOverlay").style.display = "flex";
});

// Close overlay
document.getElementById("closeHelpBtn").addEventListener("click", () => {
    document.getElementById("manualHelpOverlay").style.display = "none";
});

// Also close on clicking outside the content
document.getElementById("manualHelpOverlay").addEventListener("click", (e) => {
    if(e.target === document.getElementById("manualHelpOverlay")) {
        document.getElementById("manualHelpOverlay").style.display = "none";
    }
});

// --- Send command helper ---
const sendCommand = async (cmd) => {
    if (!serConnected) return;
    try {
        await fetch(`${window.APP_PREFIX}/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cmd }),
        });
    } catch (e) {
        console.error("Failed to send command:", e);
    }
};

// --- Quick command buttons ---
document.querySelectorAll(".quickBtn").forEach(btn => {
    btn.addEventListener("click", () => {
        const cmdType = btn.dataset.cmd;
        switch (cmdType) {
            case "start": sendCommand("0,1"); break;
            case "stop": sendCommand("0,0"); break;
            case "setTime":
                (async () => {
                    const h = document.getElementById("hours").value || 0;
                    const m = document.getElementById("minutes").value || 0;
                    await sendCommand(`9,${h}`);  // wait for first command
                    await new Promise(r => setTimeout(r, 1000)); // 50ms delay
                    await sendCommand(`10,${m}`); // then send second
                })();
                break;
            case "minTemp":
                sendCommand(`1,${document.getElementById("minTemp").value}`);
                break;
            case "maxTemp":
                sendCommand(`2,${document.getElementById("maxTemp").value}`);
                break;
            case "enableHeater": sendCommand("3,1"); break;
            case "disableHeater": sendCommand("3,0"); break;
    
            // DB LV PSU controls
            case "enableDB0": sendCommand("5,1"); break;
            case "disableDB0": sendCommand("5,0"); break;
            case "enableDB1": sendCommand("6,1"); break;
            case "disableDB1": sendCommand("6,0"); break;
            case "enableDB2": sendCommand("7,1"); break;
            case "disableDB2": sendCommand("7,0"); break;
            case "enableDB3": sendCommand("8,1"); break;
            case "disableDB3": sendCommand("8,0"); break;

            case "enablePower": sendCommand("4,1"); break;
            case "disablePower": sendCommand("4,0"); break;
            case "readSettings": sendCommand("11,1"); break;
            case "readTemp": sendCommand("14,1"); break;
            case "readVolt": sendCommand("13,1"); break;
        }
    });
});

// --- Download log ---
document.getElementById("downloadLogBtn").addEventListener("click", () => {
    window.open("/download_log", "_blank");
});

// --- Poll serial buffer every 200ms ---
setInterval(async () => {
    if (!serConnected) {
        receiveLed.classList.remove("green","blink");
        return;
    }
    try {
        const res = await fetch(`${window.APP_PREFIX}/serial`);
        const data = await res.json();

        // Append only new lines
        if (data.length > consoleBuffer.length) {
            const newLines = data.slice(consoleBuffer.length);
            newLines.forEach(line => appendConsoleLine(line));

            // Keep buffer last 500 lines
            consoleBuffer = data.slice(-500);

            // LED blink
            receiveLed.classList.add("green","blink");
        } else {
            receiveLed.classList.remove("blink");
        }

    } catch (e) {
        console.error("Error polling serial:", e);
    }
}, 200);