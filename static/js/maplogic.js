var paths = {} ;            // user paths

let user_colors = {};
var calculateRoute = null; // get directions
var user_locations = {}    // user locations
var all_markers = {        // all markers
    "suggestion": [],
    "users": {},
    "user_added_locations": [],
    "destination": null,
    "user_dests": {}
};
var current_directions;    // current directions / path
var destination = null;    // destination coordinates
var step_index = 0;        // index in path

var running_speed = 5;     // base speed
var running_delay = 150;   // move running_speed metres every X miliseconds

var colours_index = 0;     // index in colours array
var colours =              // colours array
["#9a465c",
 "#469a83",
 "#29a0b1",
 "#167d7f",
 "#98d7c2",
 "#ddffe7",
 "#9a4686",
 "#9a5946",
 "#9a8346",
 "#5c9a46"];

// Initialize google maps map
function initMap() {

    // Instantiate a directions service.
    const directionsService = new google.maps.DirectionsService();
    // Create a map
    const map = new google.maps.Map(document.getElementById("map"), {
        zoom: 14,
        center: { lat: 31.894756, lng: 34.809322 },
    });

    function update_user(data){
        var name = data.name;

        //console.log("update_user", data, name, location);
        // create latlng object
        var myLatLng = new google.maps.LatLng(data.lat, data.lng);

        // update user_locations dictionary under name
        user_locations[name] = myLatLng;

        // update/display marker in updated location
        if (name in all_markers.users)
            all_markers.users[name].setPosition(myLatLng);
        else {
            all_markers.users[name] = new google.maps.Marker({
                position: myLatLng,
                label: name,
                map: map
//                labelOrigin: new google.maps.Point(100, 10)
            });
        }
//        if(user != "Admin")
//        all_markers.users[name].setIcon(color_dot_link("red"))
        user_locations[name] = myLatLng;
        if (user==name){
        socket.emit('yes_i_got_my_loc');
        }
    }



    function _update_p_members(data){
       if(user == "Admin")
        return;
       var a = document.getElementById("party-members")
       a.innerHTML = "";
       if (data.length == 0){
            in_party = false;
            leader_of_party = false;
            party_users = [];
            return;
       }
       in_party = true;
       a.innerHTML += `<div class="hover:bg-gray-light rounded"><span style="color:red">${data[0]}</span><span style="color:white"> (owner)</span><br></div>`;
       leader_of_party = data[0] == user;
       if(leader_of_party){
        $("#start_origin").visibility = 'visible';
       }

       for(let i = 1; i < data.length; i++){
           a.innerHTML += `<div class="hover:bg-gray-light rounded"><p class="white">${data[i]}</p></div>`
       }
      a.style.visibility = 'visible';
    }




    socket.on('update_party_members', function(data){

       response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }

       for(let i = 0; i < party_users.length; i++){
           if(  !(data.includes(party_users[i]))  )
            all_markers.users[party_users[i]].setMap(null);
       }
       party_users = data;
       _update_p_members(data);
    });


















    socket.on('my_location_from_server', function(data){

        response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }
        update_user(data);

    });

      // get updated destination from the server
    socket.on('update_destination', function(data){

        response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }


        var lat = data.lat;
        var lng = data.lng;
        destination = new google.maps.LatLng(lat, lng);
        // set step_index to zero
        // since we'll have a new path
        step_index = 0;
        // calculate route
        calculateRoute();
    });

    socket.on('party_member_coords', function(data){
        response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }

//        for (const [username, marker] of Object.entries(all_markers.users)) {
//           marker.setMap(null);
//        }
        data.forEach(function(item){
            update_user(item);
//            if (!(item.name in party_users))
//                all_markers.users[item.name].setMap(null);
//            else{
                if(!item.is_online){
                    all_markers.users[item.name].setIcon(color_dot_link("yellow"));
//                }
                } else {
                    all_markers.users[item.name].setIcon(color_dot_link("red"));
                }
        });
    });



    socket.on('reset_markers', function(data){
        response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }

       var suggestion_markers = all_markers.suggestion;

       for (let i = 0; i < suggestion_markers.length; i++) {
           suggestion_markers[i].setMap(null);
       }
       for (const [username, marker] of Object.entries(all_markers.users)) {
           marker.setMap(null);
       }
       for (const [username, path] of Object.entries(all_markers.users)) {
           path.setMap(null);
       }
       all_markers.destination.setMap(null);

    });

    socket.on('party_destination', function(data){
        response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }
        var suggestion_markers = all_markers.user_dests;
        for (const [username, marker] of Object.entries(suggestion_markers)) {
          marker.setMap(null);
        };
        for (let i = 0; i < data.length; i++){
           let a = data[i];
           let name = a[1];
           let myLatLng = new google.maps.LatLng(a[i][0], a[i][1]);
           suggestion_markers[a] = new google.maps.Marker({
               position: myLatLng,
               label: "Destination",
               map: map
           });
           var icon = {
                url: all_markers.users[name].icon.url,
                scaledSize: new google.maps.Size(40, 40), // scaled size
                origin: new google.maps.Point(0, -5), // origin
                anchor: new google.maps.Point(20, 40) // anchor
            }
           suggestion_markers[a].setIcon(icon);
       };



    });


    socket.on('location_suggestion', function(data){
       response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }
       var suggestion_markers = all_markers.suggestion;
       // reset all suggestion markers
       for (let i = 0; i < suggestion_markers.length; i++) {
           suggestion_markers[i].setMap(null);
       }
       // go over data that we received
       // from the server

       var location = data.location;
       var myLatLng = new google.maps.LatLng(location.lat, location.lng);
       var marker = new google.maps.Marker({
           position: myLatLng,
           label: data.name,
           map: map
//           icon: data.icon
       });
       suggestion_markers.push(marker);
//       }
       /* not actually needed, maybe will serve
        a purpose later. currently only prints
        the label of the marker on click event. */
       suggestion_markers.forEach(function(item){
           item.addListener('click', () => {
               console.log(item.label);
           });
       });
    });

    // start simulation button.
    // this only works when theres a path.
    $("#start_origin").on("click", function() {
        if (current_directions == null)
            return

        var unit = running_speed * 0.0000089;
        // stop simulation if we have some error
        function distance(lat1, lng1, lat2, lng2){
            return Math.sqrt((lat1-lat2)*(lat1-lat2)+(lng2-lng1)*(lng2-lng1));
        }
        function move_towards_next_point() {
            try{
                var current_pos = all_markers.users[user].getPosition().toJSON();
                var my_lat = current_pos.lat;
                var my_long = current_pos.lng;
                var next_point = current_directions[step_index];
            } catch(e){
                console.log(e);
                clearInterval(myInterval);
                console.log('stop simulation!! 1');
                return;
            }

            if(next_point == undefined || next_point == null || step_index == current_directions.length){
                clearInterval(myInterval);
                socket.on('arrived')
                console.log('arrived!')
                console.log('stopp simulation!! 2');
                return;
             }

            var new_lat = 0;
            var new_long = 0;

            var d = distance(next_point[0], next_point[1], my_lat, my_long);

            /* if a single step would go further
               than the next point, just teleport
               to it.                             */
            if (d < unit){
                new_lat = next_point[0];
                new_long = next_point[1];
                // update step index
                step_index += 1;
                // tell server we updated our
                // step index
                socket.emit('step');
                // are we finished?
                if(current_directions.length == step_index){
                    clearInterval(myInterval);
                    socket.emit('arrived')
                    console.log('arrived!')
                    return
                }
            } else {
                var percent = unit / d;
                new_lat = my_lat + (next_point[0]-my_lat) * percent;
                new_long = my_long + (next_point[1]-my_long) * percent;
            }

            // send the server our new location
            socket.emit('my_location_from_user',
                {"lat": new_lat,
                 "lng": new_long,
                 "index": step_index
                 });
       }
        var myInterval = setInterval(move_towards_next_point, running_delay);
        console.log('start simulation!!');
    });


    socket.on('user_paths', function(data){
      response = validate_message(data);
      if (response.status == "new"){
          data = response.data;
      } else {
          return;
      }

      for(let i = 0; i < data.length; i++){
          // this loop goes through users
          // get current user
          var current_user_data = data[i];
          // name
          var name = current_user_data[0];
          // path
          var user_path = current_user_data[1];
          // format path into google maps' LatLng format
          var formatted_user_path = user_path.map(x =>  new google.maps.LatLng(x.lat, x.lng));

          if (name in paths){
              paths[name].path.setMap(null);
              paths[name].path = new google.maps.Polyline({
               path: formatted_user_path,
               geodesic: true,
               strokeOpacity: 1.0,
                   strokeColor: paths[name].colour,
                   strokeWeight: 5,
                   map: map
               });
           } else{
                paths[name] = {"path": null, "colour": colours[colours_index]};
                colours_index += 1;
                colours_index %= colours.length;

                paths[name].path = new google.maps.Polyline({
                    path: formatted_user_path,
                    geodesic: true,
                    strokeOpacity: 1.0,
                    strokeColor: paths[name].colour,
                    strokeWeight: 5,
                    map: map
                });
            }
        }
    });



    socket.on('user_added_locations', function(data){
      response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }

      var user_added_locations = all_markers
                                 .user_added_locations
                                 .map(x => `${x.getPosition().lat()}, ${x.getPosition().lng()}`)
      for(let i = 0; i < data.length; i++){
           var name = data[i][0];
           var latlng = data[i][1];
           // only include new locations
           if(!user_added_locations.includes(`${latlng[0]}, ${latlng[1]}`)){
                var myLatLng = new google.maps.LatLng(latlng[0], latlng[1])
                var m = new google.maps.Marker({
                        position: myLatLng,
                        label: name,
                        map: map,
                        icon: "https://developers.google.com/maps/documentation/javascript/examples/full/images/beachflag.png"
                });
                all_markers.user_added_locations.push(m);
                user_added_locations.push(`${latlng[0]}, ${latlng[1]}`)
                all_markers.user_added_locations[i].addListener("click", () => {
                if (in_party){
                    socket.emit('request_destination_update', {"lat": all_markers.user_added_locations[i].getPosition().lat(),
                                                               "lng": all_markers.user_added_locations[i].getPosition().lng(),
                                                               "name": all_markers.user_added_locations[i].label})
                    map.setCenter(all_markers.user_added_locations[i].getPosition());
                }
                });
            }
        }
      });

    function color_dot_link(colour){
//        return "https://maps.google.com/mapfiles/ms/icons/"+ colour + "-dot.png"
        if(colour == "yellow"){
            //            return "https://maps.google.com/mapfiles/kml/paddle/pause.png";
            var icon = {
                url: "https://maps.google.com/mapfiles/kml/paddle/pause.png", // url
                scaledSize: new google.maps.Size(40, 40), // scaled size
                origin: new google.maps.Point(0, -5), // origin
                anchor: new google.maps.Point(-20, 20) // anchor
            };
            return icon;
        }
        return {
                url: "https://maps.google.com/mapfiles/kml/paddle/" + colour + "-blank.png",
                scaledSize: new google.maps.Size(40, 40), // scaled size
                origin: new google.maps.Point(0, -5), // origin
                anchor: new google.maps.Point(20, 40) // anchor
            };
//        return "https://maps.google.com/mapfiles/kml/paddle/" + colour + "-blank.png"

    }

    socket.on('user_colors', function(data){

      response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }


//      for (let i = 0; i < all_markers.users.length; i++) {
//        all_markers.users[i].setIcon(color_dot_link("red"));
//      }
      user_colors = data;
      if (user=="Admin"){
          for (const [username, marker] of Object.entries(all_markers.users)) {
                marker.setIcon(color_dot_link("red"));
          }
      }
      for (let i = 0; i < data.length; i++) {
        var color = data[i][0];
        var same_color_users = data[i][1];
        for (let j = 0; j < users.length; j++){
            if(same_color_users[j] in all_markers.users)
           all_markers.users[same_color_users[j]].setIcon(color_dot_link(color));
        }
      }
    });

    // Create a renderer for directions and bind it to the map.
    const directionsRenderer = new google.maps.DirectionsRenderer({ map: map });
    // Instantiate an info window to hold step text.
    const stepDisplay = new google.maps.InfoWindow();

    calculateRoute = function () {
        calculateAndDisplayRoute(
        directionsRenderer,
        directionsService,
        stepDisplay,
        map
        );
    };
      // Listen to change events from the start and end lists.
}


function calculateAndDisplayRoute(
  directionsRenderer,
  directionsService,
  stepDisplay,
  map
) {
    if(user == "Admin"){
    return;
    }

  // Retrieve the start and end locations and create a DirectionsRequest using
  // WALKING directions.

  if (!(user in user_locations)){
        socket.emit('user_added_locations_get');
        socket.emit('party_members_list_get');
        socket.emit('online_members_get');
        socket.emit('get_destination')
        // TEMP

        socket.emit('get_coords_of_party')
        console.log("pussy")
        return;
  } else {
  var origin = user_locations[user];
}
  if (destination != null){
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
          var myRoute = directionsData.legs[0]
          current_directions = [];
          for(let i = 0; i < myRoute.steps.length; i++){
             var step = myRoute.steps[i];
             for(let i = 0; i < step.path.length; i++){
                var coords = step.path[i];
                current_directions.push([coords.lat(), coords.lng()]);
                console.log(i, coords.lat(), coords.lng())
             }
          }
          step_index = 0;
          socket.emit('path_from_user', current_directions);
          if (leader_of_party){
            socket.emit('send_dest', destination);
          }


         all_markers.destination = new google.maps.Marker({
                        position: destination,
                        map: map,
         });
         document.getElementById('msg').innerHTML = " Walking distance is " + directionsData.legs[0].distance.text + " (" + directionsData.legs[0].duration.text + ").";
        })
    }



}

function attachInstructionText(stepDisplay, marker, text, map) {
  google.maps.event.addListener(marker, "click", () => {
    // Open an info window when the marker is clicked on, containing the text
    // of the step.
    stepDisplay.setContent(text);
    stepDisplay.open(map, marker);
  });
}

window.onbeforeunload = function () {
    socket.emit('disconnect');
    all_markers.users[user].setIcon(color_dot_link("yellow"));
    document.getElementById('overlay-dude').style.display = "block;";
    document.getElementById('main-div-dude').style.display = "none;";
//    socket.disconnect();
//    socket = null;
//    socket = io.connect('http://' + document.domain + ':' + location.port + '/comms');
//    console.log("attempted reconnect");
//    window.location.reload();
};