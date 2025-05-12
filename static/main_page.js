let MAX_DATA_COUNT = 300;

let channelCount = 2; // Static value, change manually if channel count is changed

// Pre-set colors for channels
let colors = [ "rgb(255, 0, 0)", "rgb(255, 127, 0)", "rgb(255, 255, 0)", "rgb(127, 255, 0)", "rgb(0, 255, 0)", "rgb(0, 255, 127)", "rgb(0, 255, 255)", "rgb(0, 127, 255)", "rgb(0, 0, 255)", "rgb(127, 0, 255)", "rgb(255, 0, 255)", "rgb(255, 0, 127)" ];

// Function to create new chart
function createChart(elementID){
  let createdDatasets = [];
  for(let i = 0; i < channelCount; i++){
    createdDatasets[i] = { label: "Channel " + (i+1), borderWidth: 2, borderColor: colors[i] };
  }
  return new Chart(document.getElementById(elementID).getContext("2d"), {
    type: "line",
    data: {
      datasets: createdDatasets,
    },
  });
}

// Function to add data to chart
function addNewData(chartObject, label, data){
  while(chartObject.data.labels.length > MAX_DATA_COUNT){
    chartObject.data.labels.splice(0, 1);
    chartObject.data.datasets.forEach((dataset) => {
      dataset.data.shift();
    });
  }
  chartObject.data.labels.push(label);
  for(let i = 0; i < channelCount; i++){
    chartObject.data.datasets[i].data.push(data[i]);
  }
  chartObject.update('none');
}

// Function to change data in table
function setTableData(msg){
  for(let i = 0; i < channelCount; i++){
    document.getElementById("v" + i).value = msg.voltage[i].toFixed(3);
    document.getElementById("tv" + i).value = msg.voltageTarget[i].toFixed(3);
    document.getElementById("a" + i).value = msg.amperage[i].toFixed(3);
  }
}


$(document).ready(function () {
  // Create the charts
  let VoltageChart = createChart("VoltageChart");
  let TargetVoltageChart = createChart("TargetVoltageChart");
  let AmperageChart = createChart("AmperageChart");

  // Start socket.io to get live data from server
  var socket = io.connect();

  //receive data from server and add it to the charts
  socket.on("updateSensorData", function (msg) {  
    addNewData(VoltageChart, msg.time, msg.voltage);
    addNewData(TargetVoltageChart, msg.time, msg.voltageTarget);
    addNewData(AmperageChart, msg.time, msg.amperage);
    setTableData(msg);
  });
});

// A function to change the amount of items to keep in the chart
function changeTime(document){
  MAX_DATA_COUNT = parseInt(document.getElementById("time").value);
}
