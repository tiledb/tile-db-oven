const consoleDiv = document.getElementById("console")
const connectBtn = document.getElementById("connectBtn")
const sendBtn = document.getElementById("sendBtn")
const statusDiv = document.getElementById("status")
const cmdInput = document.getElementById("cmdInput")
const portSelect = document.getElementById("port")
const baudInput = document.getElementById("baudrate")

connectBtn.addEventListener("click", connect)
sendBtn.addEventListener("click", manualSend)

document.querySelectorAll("[data-cmd]").forEach(btn => {
    btn.addEventListener("click", () => {
        send(btn.dataset.cmd)
    })
})

function connect(){
    fetch("/connect",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
            port: portSelect.value,
            baudrate: baudInput.value
        })
    })
    .then(r=>r.json())
    .then(data=>{
        if(data.status==="connected"){
            statusDiv.textContent="Connected"
            statusDiv.className="status connected"
        }else{
            statusDiv.textContent="Connection Error: " + (data.msg || "")
            statusDiv.className="status disconnected"
        }
    })
}

function send(cmd){
    fetch("/send",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({cmd:cmd})
    })
}

function manualSend(){
    send(cmdInput.value)
    cmdInput.value=""
}

function updateConsole(){
    fetch("/serial")
    .then(response=>{
        if(!response.ok) throw new Error("Server error")
        return response.json()
    })
    .then(data=>{
        consoleDiv.innerHTML=data.join("<br>")
        consoleDiv.scrollTop=consoleDiv.scrollHeight
    })
    .catch(err=>{
        console.log("Console fetch error:",err)
    })
}

setInterval(updateConsole,400)