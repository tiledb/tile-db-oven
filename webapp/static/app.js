
// ---------------------- Cytoscape Oven State Graph ----------------------
const cy = cytoscape({
    container: document.getElementById('ovenStateGraph'),
    elements: [
        // nodes
        { data: { id: 'Idle', label: 'Idle' }, position: { x: 50, y: 75 } },
        { data: { id: 'WarmUp', label: 'Warm-up' }, position: { x: 100, y: 25 } },
        { data: { id: 'BurnIn', label: 'Burn-in' }, position: { x: 300, y: 25 } },
        { data: { id: 'CoolDown', label: 'Cool-down' }, position: { x: 350, y: 75 } },
        { data: { id: 'Finished', label: 'Finished' }, position: { x: 200, y: 75 } },

        // edges
        { data: { id: 'e1', source: 'Idle', target: 'WarmUp' } },
        { data: { id: 'e2', source: 'Idle', target: 'BurnIn' } },
        { data: { id: 'e3', source: 'WarmUp', target: 'BurnIn' } },
        { data: { id: 'e4', source: 'BurnIn', target: 'WarmUp' } },
        { data: { id: 'e5', source: 'BurnIn', target: 'CoolDown' } },
        { data: { id: 'e6', source: 'BurnIn', target: 'Finished' } },
        { data: { id: 'e7', source: 'CoolDown', target: 'Idle' } }
    ],

    style: [
        {
            selector: 'node',
            style: {
                'label': 'data(label)',
                'text-valign': 'center',
                'color': '#0f0',
                'background-color': '#600',
                'width': 40,
                'height': 40,
                'font-size': 14,
                'text-outline-width': 2,
                'text-outline-color': '#0f3f6b'
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 3,
                'line-color': '#0e0ae7',
                'target-arrow-color': '#888',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier'
            }
        },
        {
            selector: '.current',
            style: {
            'background-color': '#04d361',
            'width': 50,
            'height': 50,
            'text-outline-color': '#050374',
            'transition-property': 'background-color, width, height',
            'transition-duration': '0.8s',
            'font-size': 16,
            'font-weight': 'bold'
            }
        },
        {
            selector: '.completed',
            style: {
                'background-color': '#04d361',
                'text-outline-color': '#050374'
            }
        },
        {
            selector: '.previous',
            style: {
                'background-color': '#05421c', // orange
                'width': 45,
                'height': 45,
                'text-outline-color': '#050374',
                'font-size': 16,
                'font-weight': 'bold'
            }
        },
        {
            selector: '.highlight',
            style: {
                'line-color': '#00ff66',         // bright green
                'width': 5,                       // thicker line
                'target-arrow-color': '#00ff66',  // arrow color
                'transition-property': 'line-color, width',
                'transition-duration': '0.5s'
            }
        }

    ],

    layout: {
        name: 'preset',
        fit: false // important: do not auto-fit, let positions stick
    },
    // layout: {
    //     name: 'grid',
    //     rows: 1,
    //     cols: 4,
    //     padding: 20
    // }
});

// map oven state string to node id
const stateMap = {
    '0': 'Idle',
    '1': 'WarmUp',
    '2': 'BurnIn',
    '3': 'CoolDown',
    '4': 'Finished',
};

// Keep track of completed states for history
let historyStates = [];
let previousState = null;
let currentState = null;


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
                fontSize:14,
                color:"#00ff66"
            },

            pointer:{
                width:8
            },

            detail:{
                fontSize:20,
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

function setLED(id, value){

    const el = document.getElementById(id);

    if(value === "1"){
        el.classList.add("on");
    }else{
        el.classList.remove("on");
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
            connectionLed.classList.add("on");
            connectionLed.classList.remove("red");
            connectLabel.textContent = "Device Connected";
            serConnected = true;
        } else {
            connectionLed.classList.remove("on");
            connectionLed.classList.add("red");
            connectLabel.textContent = "Waiting for device";
            serConnected = false;
        }
    } catch (e) {
        connectionLed.classList.remove("on");
        connectionLed.classList.add("red");
        connectLabel.textContent = "Backend unreachable";
        serConnected = false;
    }
};

function formatSeconds(sec){

    sec = Number(sec) || 0;

    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;

    return [
        h.toString().padStart(2,'0'),
        m.toString().padStart(2,'0'),
        s.toString().padStart(2,'0')
    ].join(':');

}

// --------------------------------------------------
// SERIAL CONSOLE POLLING
// --------------------------------------------------
setInterval(async () => {
    await updateConnectionStatus();
    if (!serConnected) {
        receiveLed.classList.remove("green", "on");
        return;
    }
    try {
        const res = await fetch(`${window.APP_PREFIX}/serial`);
        const data = await res.json();
        if (data.length > consoleBuffer.length) {
            const newLines = data.slice(consoleBuffer.length);
            newLines.forEach(line => appendConsoleLine(line));
            consoleBuffer = data.slice(-500);
            receiveLed.classList.add("green", "on");
        } else {
            receiveLed.classList.remove("on");
        }
    } catch (e) {
        console.error("Error polling serial:", e);
        receiveLed.classList.remove("green", "on");
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

        const total = 60*Number(s.RunTotalMins || 1);
        const accrued = Number(s.BurninAccruedSecs || 0);

        // Update chart data
        burninChart.setOption({
            series:[{
                data:[
                    { value: accrued, name:'Accrued', itemStyle:{color:'#00ff66'} },
                    { value: Math.max(total-accrued,0), name:'Remaining', itemStyle:{color:'#222'} }
                ],
                label: {
                    formatter: `${(accrued/total*100).toFixed(2)}%`
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
            formatSeconds(s.RunTotalMins*60) || formatSeconds(0);

        document.getElementById("statusBurninAccruedSecs").innerText =
            formatSeconds(s.BurninAccruedSecs) || formatSeconds(0);

        document.getElementById("statusRunningTime").innerText =
            formatSeconds(s.RunningTime) || formatSeconds(0);

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

        setLED("ledLVPower", s.LVPower);


        const stateNode = stateMap[s.State];
        if (previousState!== stateNode) {
        // Reset classes first
            cy.nodes().removeClass('current previous completed');
            cy.edges().removeClass('highlight');
        }
        



        if (s.BurninDone === "1") {
            // Burn-in complete: reset to initial state
            previousState = 'BurnIn';
            currentState = 'Finished'
            historyStates = [];
            cy.getElementById('BurnIn').addClass('previous');
            cy.getElementById('Finished').addClass('current');
            // highlight the last edge

            const lastEdge = cy.edges(`[source = "${previousState}"][target = "${currentState}"]`);
            lastEdge.addClass('highlight');

        } else {
            // highlight the last edge
            if(previousState && stateNode) {
                const lastEdge = cy.edges(`[source = "${previousState}"][target = "${stateNode}"]`);
                lastEdge.addClass('highlight');
            }
            // normal operation
            if (previousState && previousState !== stateNode) {
                cy.getElementById(previousState).addClass('previous');
            }

            if (stateNode) {
                cy.getElementById(stateNode).addClass('current');
                // update history
                if (!historyStates.includes(stateNode) && s.State != "1") {
                    historyStates.push(stateNode);
                }
            }

            // update previousState for next poll
            previousState = stateNode;
        }

        const graphEl = document.getElementById('ovenStateGraph');

        if(s.EnableRun === "1" && s.BurninDone === "0") {
            graphEl.classList.add('glow');
        } else {
            graphEl.classList.remove('glow');
        }

    }catch(e){
        console.error("status fetch failed",e);
    }

},1000);