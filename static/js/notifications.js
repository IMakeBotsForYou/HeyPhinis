message_logs = {};
history_logs = {};
$(document).ready(function(){
    if (user == "Admin"){
    socket.on('history_update', function(data){

        response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }


        if (data.length == 0){
            $('#history_autogenerated_div').html(`<h1 class="center_white">No history</h1>`)  ;
            return;
        }
        var final_string = "";
        var messages = data;
        for (let i = 0; i < messages.length; i++) {
            if (!messages[i]) {
                continue
            }
            var id = messages[i].id;
            var title = messages[i].title;
            var message = messages[i].message;
            var type = messages[i].type;
            var messageTime = messages[i].time;
            var display = "none";
            if(id in history_logs){
                var a = document.getElementById(`history-wrapper-${id}`);
                display = a.style.display == "none" ? "none" : "block";
            } else {
                history_logs[id] = data;
            }
            final_string += `
                <div class="mx-[10px]">
                    <div class="mb-[10px]" id="history-div-${id}">
                        <button class="collapsible mb-1" style="">${title}</button>
                        <div id="history-wrapper-${id}" class="content white" style="display: ${display};">
                            <div><p id="history_content_${id}" class="break-words" style="max-width: 90%; margin: 0 0 14px 0;"><b>${message} @<br>${messageTime}</p>
                                <div style="margin: 0 auto; text-white"></div>
                            </div>
                        </div>
                    <div>
                <div>
                <br>
            `
            }


        document.getElementById('history_autogenerated_div').innerHTML = final_string;
        var coll = document.getElementsByClassName("collapsible");
        var i;
        for (i = 0; i < coll.length; i++) {
          coll[i].addEventListener("click", function() {
            this.classList.toggle("active");
            var content = this.nextElementSibling;
            if (content.style.display == "block") {
              content.style.display = "none";
            } else {
              content.style.display = "block";
            }
          });
        }

//        var container = document.getElementById('history_autogenerated_div')
//        runScripts(container)
    });
    }






    socket.on('inbox_update', function(data){

        response = validate_message(data);
        if (response.status == "new"){
            data = response.data;
        } else {
            return;
        }


        if(user == "Admin"){
        return;
        }
        if (data.length == 0){
            $('#notification_autogenerated_div').html(`<h1 class="center_white">No messages</h1>`)  ;
            return;
        }
        var final_string = "";
        var messages = data;
        for (let i = 0; i < messages.length; i++) {
            if (!messages[i]) {
                continue
            }
            var id = messages[i].id;
            var title = messages[i].title;
            var content = messages[i].content;
            var sender = messages[i].sender;
            var type = messages[i].type;
            var display = "none";
            if(id in message_logs){
                var a = document.getElementById(`content-wrapper-${id}`).style.display;
                display = a == "none" ? "none" : "block";
            } else {
                message_logs[id] = messages[id];
            }


            final_string += `
            <div class="mb-[10px]" id="message-div-${id}">
                <button type="button" class="collapsible mb-1" style="">${title}</button>
                <div id="content-wrapper-${id}" class="content white" style="display: ${display};">
                    <div><p id="message_content_${id}" class="break-words" style="max-width: 90%; margin: 0 0 14px 0;"><b>Message from ${sender}:</b><br>${content}</p></div>
                        <div style="margin: 0 auto; text-white">
            `

            if (type == "question"){
                final_string += `
                    <button type="button" class="form_button mb-[10px] bg-white text-black hover:text-white hover:bg-black transition-300" id="confirm-button_${id}" >Accept</button>
                            <script>
                            document.getElementById("confirm-button_${id}").addEventListener("click", function() {
                               socket.emit('inbox_notification_react', {"message_id": ${id}, "reaction": "join_party"});
                               document.getElementById("message-div-${id}").remove();
                               delete message_logs[${id}]
                            });
                            </script>
                `
            }
            if (type == "group_suggestion"){
                final_string += `
                    <button type="button" class="form_button mb-[10px] bg-white text-black hover:bg-black hover:text-white transition-300" id="accept-suggestion-button_${id}" >Accept</button>
                    <button type="button" class="form_button mb-[10px] bg-white text-black hover:bg-black hover:text-white transition-300" id="reject-button_${id}" >Mark as read</button>
                        <script>
                        // accept suggestion made by server
                        document.getElementById("accept-suggestion-button_${id}").addEventListener("click", function() {
                           socket.emit('inbox_notification_react', {"message_id": ${id}, "reaction": "accept_suggestion"});                           document.getElementById("message-div-${id}").remove();
                           delete message_logs[${id}]
                        });
//                        console.log(document.getElementById("accept-suggestion-button_${id}"));
                        // reject suggestion made by server
                        document.getElementById("reject-button_${id}").addEventListener("click", function() {
                           socket.emit('inbox_notification_react', {"message_id": ${id}, "reaction": "decline_group_suggestion"});
                           document.getElementById("message-div-${id}").remove();
                           delete message_logs[${id}]
                        });
                        </script>
            `
            } else {
                final_string += `
                    <button type="button" class="form_button mb-[10px] bg-white text-black hover:bg-black hover:text-white transition-300" id="close-button_${id}" >Mark as read</button>
                    <script>
                        document.getElementById("close-button_${id}").addEventListener("click", function() {
                           socket.emit('inbox_notification_react', {"message_id": ${id}, "reaction": "decline_group_invite"});
                           document.getElementById("message-div-${id}").remove();
                           delete message_logs[${id}]
                        });
                    </script>
                `
            }

            final_string +=`
                </div>
                    </div>
                <script>
                    var x = document.getElementById("message_content_${id}");
                    x.innerHTML = \`Message from ${sender}:</b><br>${content}</p>\`
                    .replace("\\\n", "<pre>")
                    .replace("\\n", "<pre>");
                </script>
            </div>
            `
        }

        document.getElementById('notification_autogenerated_div').innerHTML = final_string;
        var coll = document.getElementsByClassName("collapsible");
        var i;
        for (i = 0; i < coll.length; i++) {
          coll[i].addEventListener("click", function() {
            this.classList.toggle("active");
            var content = this.nextElementSibling;
            if (content.style.display == "block") {
              content.style.display = "none";
            } else {
              content.style.display = "block";
            }
          });
        }

        var container = document.getElementById('notification_autogenerated_div')
        runScripts(container)
    });






var inbox_button = document.getElementById('collapse-inbox-button');
inbox_button.addEventListener("click", function() {
    var content = document.getElementById('notification_autogenerated_div');
    if (content.style.display == "block") {
      content.style.display = "none";
      inbox_button.innerHTML = `<span class="fa fa-plus"></span>`;
    } else {
      content.style.display = "block";
      inbox_button.innerHTML = `<span class="fa fa-minus"></span>`;
    }
});
if(user != "Admin"){
var party_button = document.getElementById('collapse-party-button');
party_button.addEventListener("click", function() {
    var content = document.getElementById('party-members');
    if (content.style.display == "block") {
      content.style.display = "none";
      party_button.innerHTML = `<span class="fa fa-plus"></span>`;
    } else {
      content.style.display = "block";
      party_button.innerHTML = `<span class="fa fa-minus"></span>`;
    }
});
} else {

var history_button = document.getElementById('collapse-history-button');
history_button.addEventListener("click", function() {
    var content = document.getElementById('history_autogenerated_div');
    if (content.style.display == "block") {
      content.style.display = "none";
      history_button.innerHTML = `<span class="fa fa-plus"></span>`;
    } else {
      content.style.display = "block";
      history_button.innerHTML = `<span class="fa fa-minus"></span>`;
    }
});
}
});