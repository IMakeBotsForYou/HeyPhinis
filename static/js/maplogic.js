function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}



function showSteps(directionResult, markerArray, stepDisplay, map) {
  // For each step, place a marker, and add the text to the marker's infowindow.
  // Also attach the marker to an array so we can keep track of it and remove it
  // when calculating new routes.
  const myRoute = directionResult.routes[0].legs[0];
  for (let i = 0; i < myRoute.steps.length; i++) {
    const marker = (markerArray[i] =
      markerArray[i] || new google.maps.Marker());
    marker.setMap(map);
    marker.setPosition(myRoute.steps[i].start_location);
    attachInstructionText(
      stepDisplay,
      marker,
      myRoute.steps[i].instructions,
      map
    );
  }
}


var onChangeHandler = null;
var user_locations = {}
var markerArray = [];

function initMap() {
      // Instantiate a directions service.
      const directionsService = new google.maps.DirectionsService();

      // Create a map and center it on my house.
      const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 13,
        center: { lat: 31.894756, lng: 34.809322 },
      });
      socket.on('party_member_coords', function(data){
        var request_directions = data[0];
        data = data[1];
        for(let i = 0; i < data.length; i++){
            var name = data[i][0];
            var latlng = data[i][1];
            var myLatLng = new google.maps.LatLng(latlng[0], latlng[1])

            if (name in user_locations){
                user_locations[name].location = myLatLng;
            } else {
                user_locations[name] = {"location": myLatLng}
            }

            if ('marker' in user_locations[name]){
                user_locations[name]["marker"].setPosition(myLatLng);
            } else {
                user_locations[name]["marker"] = new google.maps.Marker({
                    position: myLatLng,
                    label: name,
                    map: map
                });
            }
            if(name == "Dan"){
                document.getElementById("secret_start").value = name;
            }else{
                document.getElementById("secret_end").value = name;
            }
            if (request_directions){
            onChangeHandler();
            }
        }
    });

      // Create a renderer for directions and bind it to the map.
      const directionsRenderer = new google.maps.DirectionsRenderer({ map: map });
      // Instantiate an info window to hold step text.
      const stepDisplay = new google.maps.InfoWindow();

      onChangeHandler = function () {
          calculateAndDisplayRoute(
          directionsRenderer,
          directionsService,
          markerArray,
          stepDisplay,
          map
        );
      };
      // Listen to change events from the start and end lists.
      directionsRenderer.setMap(map); // Existing map object displays directions
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function calculateAndDisplayRoute(
  directionsRenderer,
  directionsService,
  markerArray,
  stepDisplay,
  map
) {

  // Retrieve the start and end locations and create a DirectionsRequest using
  // WALKING directions.
  secret_start = document.getElementById("secret_start").value;
  secret_end =   document.getElementById("secret_end").value;
  if(secret_end == '' || secret_start == ''){
    return;
  }
  origin = user_locations[secret_start].location;
  destination = user_locations[secret_end].location;



  directionsService
    .route({
      origin: origin,
      destination: destination,
      travelMode: google.maps.TravelMode.WALKING,
    })
    .then((result) => {
      // Route the directions and pass the response to a function to create
      // markers for each step.
      var directionsData = result.routes[0] // Get data about the mapped route
      socket.emit('directionsData', directionsData);
      document.getElementById("warnings-panel").innerHTML =
        "<b>" + directionsData.warnings + "</b>";
      directionsRenderer.setDirections(result);
      showSteps(result, markerArray, stepDisplay, map);
      document.getElementById('msg').innerHTML = " Driving distance is " + directionsData.legs[0].distance.text + " (" + directionsData.legs[0].duration.text + ").";

//      myRoute = result.routes[0].legs[0];
//        path_coords = []
//        for (let i = 0; i < myRoute.steps.length; i++) {
//            step = myRoute.steps[i]
//            for (let j = 0; j < step.path.length; j++){
//                coords = step.path[j];
//                path_coords.push({lat: coords.lat(), lng: coords.lng()});
//            }
//        }
//          // First, remove any existing markers from the map.
//        for (let i = 0; i < markerArray.length; i++) {
//          markerArray[i].setMap(null);
//        }
//        name_start = secret_start;
//        var index =0
//        var mark = user_locations[name_start].marker
//        var move_interval = setInterval(function () {
//             mark.setPosition(path_coords[index]);
//             index += 1;
//        }, 50);
    })
}

function attachInstructionText(stepDisplay, marker, text, map) {
  google.maps.event.addListener(marker, "click", () => {
    // Open an info window when the marker is clicked on, containing the text
    // of the step.
    stepDisplay.setContent(text);
    stepDisplay.open(map, marker);
  });
}