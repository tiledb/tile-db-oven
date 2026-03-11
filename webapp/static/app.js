// --------------------------------------------------
// TEMPERATURE GAUGE
// --------------------------------------------------

const tempGauge = echarts.init(document.getElementById('tempGauge'));

const gaugeOption = {

    series: [

        // TARGET POINTER (bottom)
        {
            type: 'gauge',
            min:20,
            max:80,
            radius:"95%",

            axisLine:{show:false},
            axisTick:{show:false},
            splitLine:{show:false},
            axisLabel:{show:false},

            pointer:{
                width:3,
                itemStyle:{color:"#ff8800"}
            },

            detail:{show:false},
            title:{show:false},

            data:[{value:0}]
        },

        // MAIN GAUGE (top)
        {
            type:'gauge',
            min:20,
            max:80,
            radius:"95%",

            axisLine:{
                lineStyle:{
                    width:18,
                    color:[[1,'#444']]
                }
            },
            
            axisLabel:{
                fontSize:18,
                color:"#00ff66"
            },

            pointer:{
                width:8
            },

            detail:{
                fontSize:28,
                offsetCenter:[0,"60%"],
                formatter:"{value} °C"
            },

            data:[{value:0}]
        }

    ]
};

tempGauge.setOption(gaugeOption);

// --------------------------------------------------
// BURNIN CLOCK
// --------------------------------------------------

const burninDom = document.getElementById('burninClock');
const burninChart = echarts.init(burninDom);

const burninOption = {
    series: [{
        type: 'pie',
        radius: ['70%', '90%'],
        avoidLabelOverlap: false,
        label: {
            show: true,
            position: 'center',
            formatter: '{c}%', // placeholder, will update dynamically
            color: '#00ff66',
            fontSize: 24,
            fontWeight: 'bold'
        },
        labelLine: { show: false },
        silent: true,
        data: [
            { value: 0, name: 'Accrued', itemStyle:{color:'#00ff66'} },
            { value: 1, name: 'Remaining', itemStyle:{color:'#222'} }
        ]
    }]
};

burninChart.setOption(burninOption);


function setLED(id, state){
    const led = document.getElementById(id);
    if(!led) return;

    if(Number(state) === 1){
        led.classList.add("green");
        led.classList.remove("red");
    }else{
        led.classList.remove("green");
        led.classList.add("red");
    }
}

let serConnected = false;
let consoleBuffer = [];

// DOM elements
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

    // keep last 500 lines
    while (consoleOutput.children.length > 500) {
        consoleOutput.removeChild(consoleOutput.firstChild);
    }

    const container = consoleOutput.parentElement;
    container.scrollTop = container.scrollHeight;
};

// --- Manual command send button ---
sendBtn.addEventListener("click", async () => {
    const cmd = manualCmd.value.trim();
    if (!cmd) return;
    if (!serConnected) {
        appendConsoleLine("ERROR: Serial device not connected");
        return;
    }
    try {
        await sendCommand(cmd);
        appendConsoleLine("> " + cmd);
        manualCmd.value = "";
    } catch (e) {
        console.error(e);
        appendConsoleLine("ERROR sending command");
    }
});

// --- ENTER key sends command ---
manualCmd.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        sendBtn.click();
    }
});

// --- Send command helper ---
const sendCommand = async (cmd) => {
    if (!serConnected) return;
    try {
        await fetch(`${window.APP_PREFIX}/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cmd })
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
            case "setTime": (async () => {
                const h = document.getElementById("hours").value || 0;
                const m = document.getElementById("minutes").value || 0;
                await sendCommand(`9,${h}`);
                await new Promise(r => setTimeout(r, 1000));
                await sendCommand(`10,${m}`);
            })(); break;
            case "minTemp": sendCommand(`1,${document.getElementById("minTemp").value}`); break;
            case "maxTemp": sendCommand(`2,${document.getElementById("maxTemp").value}`); break;
            case "targetTemp": sendCommand(`12,${document.getElementById("targetTemp").value}`); break;
            case "enableHeater": sendCommand("3,1"); break;
            case "disableHeater": sendCommand("3,0"); break;
            case "enablePower": sendCommand("4,1"); break;
            case "disablePower": sendCommand("4,0"); break;
            case "enableDB0": sendCommand("5,1"); break;
            case "disableDB0": sendCommand("5,0"); break;
            case "enableDB1": sendCommand("6,1"); break;
            case "disableDB1": sendCommand("6,0"); break;
            case "enableDB2": sendCommand("7,1"); break;
            case "disableDB2": sendCommand("7,0"); break;
            case "enableDB3": sendCommand("8,1"); break;
            case "disableDB3": sendCommand("8,0"); break;
            case "readSettings": sendCommand("11,1"); break;
            case "readVolt": sendCommand("13,1"); break;
            case "readTemp": sendCommand("14,1"); break;
        }
    });
});

// --- Download log ---
document.getElementById("downloadLogBtn").addEventListener("click", () => {
    window.open(`${window.APP_PREFIX}/download_log`, "_blank");
});

// --- Manual command help ---
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

// --- Help overlay controls ---
document.getElementById("manualHelp").addEventListener("click", () => {
    document.getElementById("manualHelpOverlay").style.display = "flex";
});
document.getElementById("closeHelpBtn").addEventListener("click", () => {
    document.getElementById("manualHelpOverlay").style.display = "none";
});
document.getElementById("manualHelpOverlay").addEventListener("click", (e) => {
    if (e.target === document.getElementById("manualHelpOverlay")) {
        document.getElementById("manualHelpOverlay").style.display = "none";
    }
});

// --------------------------------------------------
// CONNECTION STATUS POLLING
// --------------------------------------------------
const updateConnectionStatus = async () => {
    try {
        const res = await fetch(`${window.APP_PREFIX}/connection_status`);
        const data = await res.json();
        if (data.status === "connected") {
            connectionLed.classList.add("green");
            connectionLed.classList.remove("red");
            connectLabel.textContent = "Device Connected";
            serConnected = true;
        } else {
            connectionLed.classList.remove("green");
            connectionLed.classList.add("red");
            connectLabel.textContent = "Waiting for device";
            serConnected = false;
        }
    } catch (e) {
        connectionLed.classList.remove("green");
        connectionLed.classList.add("red");
        connectLabel.textContent = "Backend unreachable";
        serConnected = false;
    }
};

// --------------------------------------------------
// SERIAL CONSOLE POLLING
// --------------------------------------------------
setInterval(async () => {
    await updateConnectionStatus();
    if (!serConnected) {
        receiveLed.classList.remove("green", "blink");
        return;
    }
    try {
        const res = await fetch(`${window.APP_PREFIX}/serial`);
        const data = await res.json();
        if (data.length > consoleBuffer.length) {
            const newLines = data.slice(consoleBuffer.length);
            newLines.forEach(line => appendConsoleLine(line));
            consoleBuffer = data.slice(-500);
            receiveLed.classList.add("green", "blink");
        } else {
            receiveLed.classList.remove("blink");
        }
    } catch (e) {
        console.error("Error polling serial:", e);
        receiveLed.classList.remove("green", "blink");
    }
}, 2000);

// --------------------------------------------------
// OVEN STATUS POLLING (from server)
// --------------------------------------------------
setInterval(async () => {

    try{
        const res = await fetch(`${window.APP_PREFIX}/oven_status`);
        const s = await res.json();

        // -----------------------------
        // Temperature Gauge
        // -----------------------------

        const t = Number(s.Toven || 0);
        const tmin = Number(s.Tmin || 0);
        const tmax = Number(s.Tmax || 100);
        const ttarget = Number(s.Ttarget || 0);

        // pointer color depending on range
        let ovenColor = "#ffaa00";

        if (t < tmin) ovenColor = "#3399ff";
        else if (t > tmax) ovenColor = "#ff3333";
        else ovenColor = "#ffaa00";

        tempGauge.setOption({

            series:[
                {
                    data:[{value:ttarget}]   // bottom gauge
                },
                {
                    axisLine:{
                        lineStyle:{
                            width:18,
                            color:[
                                [(tmin-20)/60,"#3399ff"],
                                [(tmax-20)/60,"#ffaa00"],
                                [1,"#ff3333"]
                                ]
                            }
                        },

                    detail:{color:ovenColor},

                    pointer:{
                        itemStyle:{color:ovenColor}
                    },

                    data:[{value:t}]
                }
            ]

        });

        document.getElementById("labelTmin").innerText = tmin;
        document.getElementById("labelTmax").innerText = tmax;
        document.getElementById("labelTtarget").innerText = ttarget;
        document.getElementById("labelToven").innerText = t;

        // -----------------------------
        // Burn-in clock
        // -----------------------------

        const total = Number(s.RunTotalMins || 1);
        const accrued = Number(s.BurninAccruedMins || 0);

        // Update chart data
        burninChart.setOption({
            series:[{
                data:[
                    { value: accrued, name:'Accrued', itemStyle:{color:'#00ff66'} },
                    { value: Math.max(total-accrued,0), name:'Remaining', itemStyle:{color:'#222'} }
                ],
                label: {
                    formatter: `${Math.round(accrued/total*100)}%`
                }
            }]
        });



        const tempGaugeEl = document.getElementById('tempGauge');
        const burninClockEl = document.getElementById('burninClock');

        // inside your interval
        if(s.EnableRun === "1" && s.BurninDone === "0") {
            tempGaugeEl.classList.add('glow');
            burninClockEl.classList.add('glow');
        } else {
            tempGaugeEl.classList.remove('glow');
            burninClockEl.classList.remove('glow');
        }

        // -----------------------------
        // Clock labels
        // -----------------------------

        document.getElementById("statusRunTotalMins").innerText =
            s.RunTotalMins || 0;

        document.getElementById("statusBurninAccruedMins").innerText =
            s.BurninAccruedMins || 0;

        document.getElementById("statusRunningTime").innerText =
            s.RunningTime || 0;

        // -----------------------------
        // LEDs
        // -----------------------------

        setLED("ledHeater", s.EnableHeater);
        setLED("ledRun", s.EnableRun);
        setLED("ledBurninDone", s.BurninDone);

        setLED("ledLV0", s.LV0);
        setLED("ledLV1", s.LV1);
        setLED("ledLV2", s.LV2);
        setLED("ledLV3", s.LV3);

    }catch(e){
        console.error("status fetch failed",e);
    }

},1000);