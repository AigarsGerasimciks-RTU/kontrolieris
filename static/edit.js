document.getElementById("selector").onchange = function() {updateSelector()}
function updateSelector(){
	var ch = document.getElementById("selector").value;
	location.replace("/edit?ch=" + ch)
}
