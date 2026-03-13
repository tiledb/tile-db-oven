// ---------------------- Cytoscape Oven State Graph ----------------------
const cy = cytoscape({
    container: document.getElementById('ovenStateGraph'),
    elements: [
        { data: { id: 'Idle', label: 'Idle' }, position: { x: 50, y: 75 } },
        { data: { id: 'WarmUp', label: 'Warm-up' }, position: { x: 100, y: 25 } },
        { data: { id: 'BurnIn', label: 'Burn-in' }, position: { x: 300, y: 25 } },
        { data: { id: 'CoolDown', label: 'Cool-down' }, position: { x: 350, y: 75 } },
        { data: { id: 'Finished', label: 'Finished' }, position: { x: 200, y: 75 } },

        { data: { id: 'e1', source: 'Idle', target: 'WarmUp' } },
        { data: { id: 'e2', source: 'Idle', target: 'BurnIn' } },
        { data: { id: 'e3', source: 'WarmUp', target: 'BurnIn' } },
        { data: { id: 'e4', source: 'BurnIn', target: 'WarmUp' } },
        { data: { id: 'e5', source: 'BurnIn', target: 'CoolDown' } },
        { data: { id: 'e6', source: 'BurnIn', target: 'Finished' } },
        { data: { id: 'e7', source: 'CoolDown', target: 'BurnIn' } },
        { data: { id: 'e8', source: 'CoolDown', target: 'Idle' } }
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
                'font-weight': 'bold'
            }
        },
        {
            selector: '.previous',
            style: {
                'background-color': '#05421c',
                'width': 45,
                'height': 45
            }
        },
        {
            selector: '.highlight',
            style: {
                'line-color': '#00ff66',
                'width': 5,
                'target-arrow-color': '#00ff66'
            }
        }
    ],

    layout: {
        name: 'preset',
        fit: false
    },

    userZoomingEnabled: false,
    userPanningEnabled: false,
    boxSelectionEnabled: false,
    autoungrabify: true
});

const stateMap = {
    '0': 'Idle',
    '1': 'WarmUp',
    '2': 'BurnIn',
    '3': 'CoolDown',
    '4': 'Finished',
};

let previousState = null;
let historyStates = [];

// --------------------------------------------------
// TEMPERATURE GAUGE
// --------------------------------------------------

const tempGauge = echarts.init(document.getElementById('tempGauge'));

const gaugeOption = {
    series: [
        {
            type: 'gauge',
            min:20,
            max:80,
            radius:"95%",
            axisLine:{show:false},
            axisTick:{show:false},
            splitLine:{show:false},
            axisLabel:{show:false},
            pointer:{width:3,itemStyle:{color:"#ff8800"}},
            detail:{show:false},
            title:{show:false},
            data:[{value:0}]
        },
        {
            type:'gauge',
            min:20,
            max:80,
            radius:"95%",
            axisLine:{lineStyle:{width:18,color:[[1,'#444']]}},
            axisLabel:{fontSize:14,color:"#00ff66"},
            pointer:{width:8},
            detail:{fontSize:20,offsetCenter:[0,"60%"],formatter:"{value} °C"},
            data:[{value:0}]
        }
    ]
};

tempGauge.setOption(gaugeOption);

// --------------------------------------------------
// BURNIN CLOCK
// --------------------------------------------------

const burninChart = echarts.init(document.getElementById('burninClock'));

const burninOption = {
    series: [{
        type: 'pie',
        radius: ['70%', '90%'],
        label: {
            show: true,
            position: 'center',
            formatter: '{c}%',
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

// --------------------------------------------------
// LEDs
// --------------------------------------------------

function setLED(id, value){
    const el = document.getElementById(id);
    if(value === "1"){
        el.classList.add("on");
    } else {
        el.classList.remove("on");
    }
}

// --------------------------------------------------
// CONNECTION STATUS
// --------------------------------------------------

const connectionLed = document.getElementById("connectionLed");

async function updateConnectionStatus(){

    try{
        const res = await fetch(`${window.APP_PREFIX}/connection_status`);
        const data = await res.json();

        if(data.status === "connected"){
            connectionLed.classList.add("on");
            connectionLed.classList.remove("red");
        }else{
            connectionLed.classList.remove("on");
            connectionLed.classList.add("red");
        }

    }catch(e){
        connectionLed.classList.remove("on");
        connectionLed.classList.add("red");
    }
}

// --------------------------------------------------
// SERIAL CONSOLE
// --------------------------------------------------

let consoleBuffer = [];
const consoleOutput = document.getElementById("consoleOutput");
const receiveLed = document.getElementById("receiveLed");

function appendConsoleLine(line){

    const div = document.createElement("div");
    div.textContent = line;
    consoleOutput.appendChild(div);

    while(consoleOutput.children.length > 500){
        consoleOutput.removeChild(consoleOutput.firstChild);
    }

    const container = consoleOutput.parentElement;
    container.scrollTop = container.scrollHeight;
}

setInterval(async () => {

    await updateConnectionStatus();

    try{

        const res = await fetch(`${window.APP_PREFIX}/serial`);
        const data = await res.json();

        const newLines = data.filter(line => !consoleBuffer.includes(line));

        if(newLines.length > 0){

            newLines.forEach(line => appendConsoleLine(line));

            consoleBuffer = [...consoleBuffer, ...newLines].slice(-500);

            receiveLed.classList.add("green","on");

        }else{

            receiveLed.classList.remove("on");

        }

    }catch(e){

        console.error("Serial poll failed",e);
        receiveLed.classList.remove("green","on");

    }

},2000);

// --------------------------------------------------
// OVEN STATUS POLLING
// --------------------------------------------------

setInterval(async () => {

    try{

        const res = await fetch(`${window.APP_PREFIX}/oven_status`);
        const s = await res.json();

        const t = Number(s.Toven || 0);
        const tmin = Number(s.Tmin || 0);
        const tmax = Number(s.Tmax || 100);
        const ttarget = Number(s.Ttarget || 0);

        let ovenColor="#ffaa00";

        if(t < tmin) ovenColor="#3399ff";
        else if(t > tmax) ovenColor="#ff3333";

        tempGauge.setOption({
            series:[
                { data:[{value:ttarget}] },
                {
                    detail:{color:ovenColor},
                    pointer:{itemStyle:{color:ovenColor}},
                    data:[{value:t}]
                }
            ]
        });

        document.getElementById("labelTmin").innerText = tmin;
        document.getElementById("labelTmax").innerText = tmax;
        document.getElementById("labelTtarget").innerText = ttarget;
        document.getElementById("labelToven").innerText = t;

        const total = 60*Number(s.RunTotalMins || 1);
        const accrued = Number(s.BurninAccruedSecs || 0);

        burninChart.setOption({
            series:[{
                data:[
                    { value: accrued, itemStyle:{color:'#00ff66'} },
                    { value: Math.max(total-accrued,0), itemStyle:{color:'#222'} }
                ],
                label:{formatter:`${(accrued/total*100).toFixed(2)}%`}
            }]
        });

        document.getElementById("statusBatchId").innerText = s.BatchId || "-";
        document.getElementById("statusRunTotalMins").innerText = s.RunTotalMins || "0";
        document.getElementById("statusBurninAccruedSecs").innerText = s.BurninAccruedSecs || "0";
        document.getElementById("statusRunningTime").innerText = s.RunningTime || "0";

        setLED("ledHeater", s.EnableHeater);
        setLED("ledRun", s.EnableRun);
        setLED("ledBurninDone", s.BurninDone);
        setLED("ledLV0", s.LV0);
        setLED("ledLV1", s.LV1);
        setLED("ledLV2", s.LV2);
        setLED("ledLV3", s.LV3);
        setLED("ledLVPower", s.LVPower);

        const stateNode = stateMap[s.State];

        cy.nodes().removeClass('current previous');
        cy.edges().removeClass('highlight');

        if(previousState && stateNode){

            cy.getElementById(previousState).addClass('previous');
            const edge = cy.edges(`[source = "${previousState}"][target = "${stateNode}"]`);
            edge.addClass('highlight');

        }

        if(stateNode){
            cy.getElementById(stateNode).addClass('current');
        }

        previousState = stateNode;

    }catch(e){

        console.error("Status fetch failed",e);

    }

},1000);