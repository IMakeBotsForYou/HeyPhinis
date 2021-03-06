# general use modules
from threading import Thread
from time import time, sleep
import numpy as np
from time import gmtime, strftime
from engineio.payload import Payload
# flask modules
from flask import *
from flask_socketio import SocketIO, emit

# my modules / warppers
from get_query_results import find_places
from database_wrapper import smallest_free
from database_wrapper import my_db as database
from kmeans_wrapper import category_values, KMEANS

Payload.max_decode_packets = 50

# message_ids = {}
# """
# message_ids[id] = {
#                     message data
#                   }
# """

popular_places = {}
chat_rooms = {"0": {"name": "Global", "history": [], "members": {}, "type": "global"}}
"""
chat_rooms[id] = {
                  "name": str,
                  "members": {name: confirmed(bool), name: confirmed(bool), ...},
                  "history" : [
                               {"author": name, "message": message},
                               ... 
                              ]
                }
"""

delete_chats_queue = {}
"""
delete_chats_queue = {
                        user: [chat_id, ...],
                        ...
                     }
"""

members = {}
"""
members[name] = {
                 "sid": // # the socket sid
                 "loc": [lat, lng],
                 "current_path": [path, index],
                 "party": name # (party owner's name),
                 "last ping": time_now(),
                 "chats": [chat_id, ...]
                }
When a user comes back online we can restore their data
from this dictionary, and update their socket SID
"""
# Subset of members that are online.
connected_members = {}

parties = {}
"""
parties[party_owner] = {
                        "members: [member, ...],
                        "destination": [lat, lng] | None
                        "vote_status": {"suggested_location": [lat, lng] | None,
                                        "during_vote": False, 
                                        "voted_yes": [member, ...],
                                        "voted_no":  [member, ...]
                                        }
                        "destination_status": "No Destination" | "Have Destination" | "Reached Destination",
                        "arrived": []
                       }
"""

party_suggestions = {}
"""
party_suggestions[party_owner] = {
                                  "members": [member, ...],                        
                                  }

"""

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret!'
app.config['DEBUG'] = True

# turn the flask app into a socketio app
socketio = SocketIO(app, async_mode=None, logger=True, engineio_logger=True, async_handlers=True)


# I don't wanna use the usual logger so I'll just make my own
def log(*args, _type="[LOG]", format="time\ttype\tmessage"):
    message = " ".join([str(a) for a in args])
    _time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    print(format.replace("time", _time)
          .replace("type", _type)
          .replace("message", message))


# def send_all_data_to_everyone():
#     pass
#     global app
#     with app.app_context():
#         while 1:
#             sleep(1)
#
#             for user in connected_members:
#                 emit_to(user=user, event_name=event_name,
#                         message=message, namespace=namespace)


#         for message_id, data in message_ids.copy().items():
#             user, event_name, message, namespace = data.copy().values()
#             custom_id = message["__message_id"]
#             message = message["__payload"]
#             emit_to(user=user, event_name=event_name,
#                     message=message, namespace=namespace,
#                     add_to_list=False, custom_id=custom_id)


def filter_dict(d: dict, f) -> dict:
    """ Filters dictionary d by function f. """
    new_dict = dict()

    # Iterate over all (k,v) pairs in names
    for key, value in d.items():

        # Is condition satisfied?
        if f(key):
            new_dict[key] = value

    return new_dict.copy()


def get_all_user_chats(target: str) -> list:
    return [{"id": room, **chat_rooms[room]}
            for room in connected_members[target]["chats"]]


def suggest_party(users: list) -> None:
    log(f"suggesting party for {users}")
    party_suggestions[users[0]] = {"total": users, "accepted": [], "rejected": []}
    for u in users:
        u_list = users.copy()
        u_list.remove(u)
        base = "The system has invited you to join a party"
        addition = f"with {', '.join(u_list[:-1])}, and {u_list[-1]}" if len(u_list) > 1 else f"with {u_list[0]}"
        desc = f"{base} {addition}"
        database.send_message(title=f"Party suggestion! {addition}",
                              desc=desc,
                              sender="Admin", receiver=u, messagetype="group_suggestion",
                              action=f"accept_suggestion/{users[0]}")

    database.add_admin_message(type="p_sug", title=f"Suggested party to {users}", message=f"Suggested party to {users}",
                               time=strftime("%Y-%m-%d %H:%M:%S", gmtime()))


def get_place_recommendation_location(tp: str, radius: float, limit: int) -> dict:
    radius = float(radius * 1000)
    limit = int(limit)

    middle_lat, middle_lng = sum(
        [connected_members[member]["loc"][0] for member in get_party_members(session['user']) if
         member in connected_members]) / len(get_party_members(session['user'])), \
                             sum([connected_members[member]["loc"][1] for member in get_party_members(session['user'])
                                  if member in connected_members]) / len(get_party_members(session['user']))
    middle = middle_lat, middle_lng

    results_json = find_places(middle, radius, tp, limit)

    return results_json


def create_chat(*, name: str, party_members: list = None) -> str:
    smallest_free_chat_id = str(len(list(chat_rooms.keys())))

    parties[party_members[0]]["chat_id"] = smallest_free_chat_id
    chat_rooms[smallest_free_chat_id] = {"name": name,
                                         "members": {m: False for m in party_members},
                                         "history": []}

    for member in party_members:
        connected_members[member]["chats"].append(smallest_free_chat_id)

    return smallest_free_chat_id


def separate_into_colours(group_owners: list) -> list:
    # colors = ['grn', 'orange', 'fuchsia', 'magenta', 'olive', 'teal', 'violet',
    #           'skyblue', 'gray', 'darkorange', 'cyan', 'royal_blue']
    colors = ['blu', 'grn', 'pink', 'whit', 'purple']
    colors_amount = len(colors)
    ret = []
    for i, g in enumerate(sorted(group_owners)):
        ret.append((colors[i % colors_amount], parties[g]["members"]))
    return ret


def create_party(user: str, members_to_add=None) -> str:
    if members_to_add is None:
        members_to_add = []
    party_members = [user] + members_to_add
    """
parties[party_owner] = {
                        "members: [member, ...],
                        "destination": [lat, lng] | None
                        "vote_status": {"suggested_location": [lat, lng] | None,
                                        "during_vote": False, 
                                        "voted_yes": [member, ...],
                                        "voted_no":  [member, ...]
                                        }
                        "destination_status": "No Destination" | "Have Destination" | "Reached Destination",
                        "arrived": []
                       }
    """
    parties[user] = {
        "members": party_members,
        "destination": None,
        "vote_status": {
            "suggested_location": None,
            "during_vote": False,
            "voted_yes": [],
            "voted_no": []
        },
        "destination_status": "No Destination",
        "arrived": []
    }

    for m in party_members:
        connected_members[m]['party'] = user
        database.add_to_party(owner=user, user_to_add=m)

    chat_id = create_chat(name="Party", party_members=party_members)

    emit_to(user=session['user'], event_name="party_members_list_get",
            message=get_party_members(session['user']))
    log(f"created party for {party_members} ID:{chat_id}")
    return chat_id


def time_now() -> int:
    return int(time())


def get_party_leader(username: str) -> str:
    if username == "Admin":
        return "Admin"

    # a = [person for person in parties if username in parties[person]["members"]]
    return connected_members[username]["party"]


def get_messages(user: str) -> dict:
    info = database.get_messages(user)
    # if user in info:
    #     return [[message['id'], message['title'], message['content'], message['sender'], message['type']]
    #             for message in info['messages'][session['user']]]
    return info


def get_party_members(username: str) -> list:
    owner = get_party_leader(username)
    if owner not in parties:
        return []
    log(username, parties[owner]["members"], _type="[PARTY MEMBERS]")
    return parties[owner]["members"].copy()


def split_interests(input_str: str) -> list:
    return [float(x) for x in input_str.split("|")[1::2]]


def prepare_kmeans_values() -> dict:
    users_and_interests = database.get(table="users",
                                       column="username,interests",
                                       first=False)

    vls = {username: split_interests(interests) for
           username, interests in users_and_interests}

    return vls


kmeans = KMEANS(vls=prepare_kmeans_values(), k=3)

"""
HELPER FUNCTIONS FOR EMITTING (SOCKET.IO) PURPOSES
"""


def emit_to(user: str, event_name: str, message=None,
            namespace: str = '/', verbose=True) -> None:
    # add_to_list=True, custom_id=None) -> None:

    # temp
    if user == "Admin" and "Admin" not in connected_members:
        return

    try:
        """    if custom_id is None:
                keys = list(message_ids.keys())
                new_id = len(keys)
            else:
                new_id = custom_id
            message = {"__message_id": new_id, "__payload": message}
            if add_to_list:
                message_ids[new_id] = {"user": user,
                                       "event_name": event_name,
                                       "message": message,
                                       "namespace": namespace}
        """

        emit(event_name, message, namespace=namespace, room=members[user]['sid'])
        if verbose:
            log(f"Sent to data: {user}: {event_name} {message} {namespace} ")
    except Exception as e:
        log(f'Error in emitting to user {user},', e, _type="[ERROR]")
        log(f'Tried to send: ', event_name, message, _type="[ERROR]")


def emit_to_everyone(**kwargs) -> None:
    [emit_to(user=m, **kwargs) for m in connected_members]


def emit_to_party(member: str, **kwargs) -> None:
    party_members = get_party_members(member)
    [emit_to(user=m, **kwargs) for m in party_members]


def send_user_added_locations(username: str) -> None:
    data = [(name, [float(value) for value in latlng.split(", ")], location_type)
            for name, latlng, location_type in database.get_user_added_locations()]
    emit_to(username, 'user_added_locations', message=data)


def party_coords(username: str) -> None:
    if username is None:
        return

    party_members = get_party_members(username)
    data = []

    for member in party_members:
        try:
            lat, lng = members[member]["loc"]
            data.append({"name": member,
                         "lat": lat, "lng": lng,
                         "is_online": member in connected_members})
        except Exception as e:
            log("get coords error", e, members, _type="[ERROR]")

    if data:
        emit_to_party(username, event_name="update_party_members", message=[x["name"] for x in data])

        emit_to_party(username, event_name='party_member_coords', message=data)


def disconnect_user_from_party(user: str, chat_is_disbanded=False) -> None:
    # Get current leader
    current_leader = get_party_leader(user)
    # Get party members
    all_members = get_party_members(current_leader)
    log('disconnecting', user, 'from', current_leader)

    # Send message to party, announcing the user that left
    send_message_to_party(current_leader, f"{user} left!")

    # If user leaving is the leader
    if current_leader == user:
        if len(all_members) == 1:
            # Disband party, kick last user
            chat_is_disbanded = True
        else:

            # Remove user from members
            all_members.remove(user)
            # Pick new leader
            new_leader = all_members[0]
            # Copy over the party data to entry
            # On new leader's name
            parties[new_leader] = parties[user].copy()
            # Remove the user from the new party
            parties[new_leader]['members'].remove(user)
            # Send update message to party about the new leader
            send_message_to_party(new_leader, f"{new_leader} is now the party leader")
            # Change current_leader to the new leader
            current_leader = new_leader
            emit_to(user, event_name="update_party_members", message=[])

    # If the chat is disbanded
    if chat_is_disbanded:
        # Update leader's party members to an empty array
        emit_to(current_leader, event_name="update_party_members", message=[])

        # Add chat_id to delete queue
        if user not in delete_chats_queue:
            delete_chats_queue[user] = [get_party_chat_id(current_leader)]
        else:
            delete_chats_queue[user].append(get_party_chat_id(current_leader))

        # delete chatroom
        del delete_chats_queue[get_party_chat_id(current_leader)]
        # delete party entry
        del parties[current_leader]
    else:
        # Not disbanded, keep the chatroom and party entry
        # Add chat_id to delete chat queue
        if user not in delete_chats_queue:
            delete_chats_queue[user] = [get_party_chat_id(current_leader)]
        else:
            delete_chats_queue[user].append(get_party_chat_id(current_leader))

        # Remove user from party members
        try:
            parties[current_leader]["members"].remove(user)
        except (ValueError, KeyError):
            log("already removed :)", _type="[WARNING]")
        # Send to remaining party to update member list
        members = get_party_members(current_leader)
        emit_to_party(current_leader, event_name="update_party_members", message=members)
    connected_members[user]["party"] = None
    emit_to(user, event_name="reset_markers")


def update_destination(data, user):
    leader = get_party_leader(user)
    if not leader:
        return
    parties[leader]["destination"] = data
    parties[leader]["destination_status"] = "Has Destination"
    parties[leader]["arrived"] = []

    emit_to_party(user, event_name='update_destination',
                  message=data)


def start_vote_on_place(leader, location_data, add_marker=True):
    parties[leader]["in_vote"] = True
    parties[leader]["votes"] = {}

    if "location" in location_data:
        loc = location_data["location"]
        location_data["lat"] = loc["lat"]
        location_data["lng"] = loc["lng"]

    parties[leader]["destination"] = [location_data["lat"], location_data["lng"]]
    send_message_to_party(session['user'],
                          message=f"How about < {location_data['name']} > ?  Vote now! (/vote y) ")

    if location_data["name"] not in popular_places:
        popular_places[location_data['name']] = 0
    else:
        popular_places[location_data['name']] += 1

    if add_marker:
        emit_to_party(leader, event_name='location_suggestion', message=location_data)
        emit_to("Admin", event_name='party_destination',
                message=[(parties[leader]['destination'], leader) for leader in parties])


def parse_chat_command(command, chat_id):
    # try:
    args = command[1:].split(" ")

    in_party_chat = chat_id == get_party_chat_id(session['user'])

    if len(args) > 1:
        cmd, arguments = args[0], args[1:]
    else:
        cmd, arguments = args[0], []

    if cmd == "vote" and in_party_chat:

        party_owner = get_party_leader(session['user'])
        vote_status = parties[party_owner]["votes"]
        if session["user"] in vote_status or not parties[party_owner]["in_vote"]:
            # already voted
            return

        decision = arguments[0].lower() in ["yes", "y"]
        vote_status[session["user"]] = decision
        votes_required = int(len(parties[party_owner]["members"]) / 2) + 1
        # filter function, vote_status[x] == True -> voted yes
        have_voted_yes = lambda x: vote_status[x]
        send_message_to_party(party_owner, message=f'{session["user"]} has voted {"Yes" if decision else "No"}. '
                                                   f'({len(filter_dict(vote_status, have_voted_yes).keys())}/'
                                                   f'{votes_required})')

        # A majority has voted to some either go or not go
        voted_yes = [name for name in vote_status if vote_status[name]]
        voted_no = [name for name in vote_status if not vote_status[name]]

        # Vote has resulted in rejecting the sever's suggestion
        if len(voted_no) > len(parties[party_owner]["members"]) - votes_required:
            send_message_to_party(session['user'],
                                  message=f"{len(voted_no)} people have voted NO.<br>"
                                          f"Vote canceled. You can request another suggestion.")
            parties[party_owner]["in_vote"] = False

        if votes_required == len(voted_yes):
            lat, lng = parties[party_owner]["destination"]
            update_destination({"lat": lat, "lng": lng}, session['user'])

            send_message_to_party(session['user'],
                                  message=f"{len(voted_yes)} people have voted YES.<br>"
                                          f"Calculating route...")
            parties[party_owner]["in_vote"] = False

    if cmd == "sug" and in_party_chat:
        # lat, lng = get_location_request(session['user'])
        # location = {"name": "De-Shalit High-school", "lat": 31.89961596028198, "lng": 34.816320411774875}
        leader = get_party_leader(session['user'])
        # reset votes and update status to during vote (in vote)
        parties[leader]["in_vote"] = True
        parties[leader]["votes"] = {}
        # radius is in KM(Kilometres)
        locations = get_place_recommendation_location(
            tp=parties[leader]["place_type"],
            radius=2,
            limit=10
        )
        index = np.random.randint(0, len(locations))
        location = locations[index]

        start_vote_on_place(leader=leader,
                            # lat=loc_of_place["lat"],
                            # lng=loc_of_place["lng"],
                            # name=location['name'],
                            location_data=location)



    if cmd == "leave_group" and in_party_chat:
        disconnect_user_from_party(session['user'])

    if cmd == "disband" and in_party_chat:
        if session['user'] == get_party_leader(session['user']):
            chat_id = get_party_chat_id(session['user'])
            # First disconnect everyone else
            emit_to_party(session['user'], event_name="update_party_members", message=[])
            # Get party members
            users_without_admin = get_party_members(session['user'])
            # Remove admin
            users_without_admin.remove(session['user'])
            # Disconnect everyone else
            [disconnect_user_from_party(u) for u in users_without_admin]
            # Then disconnect you
            disconnect_user_from_party(session['user'])
            # Not a trace ....
            del parties[session['user']]
            chat_rooms[chat_id] = {"members": []}


"""
====================================================
 
              WEBSITE ENDPOINTS 
"""


#  LANDING PAGE
@app.route("/", methods=["POST", "GET"])
def main_page():
    session["time"] = int(time())
    # If user is not logged in
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("main.html")


#  REGISTER PAGE
@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        # get info from form
        user = request.form['name']
        password = request.form['pass']
        confirm = request.form['confirm']
        all_names = database.get_all_names()
        if user in all_names:
            flash('This name is already taken.', category='error')
        elif len(user) < 2:
            flash('Name must be longer than 1 character.', category='error')
        elif password != confirm:
            flash('Passwords don\'t match.', category='error')
        # elif len(password) < 7:
        #     flash('Password must be at least 7 characters.', category='error')
        else:
            session['user'] = user
            database.add_user(user, password)
            return redirect("/")
        return render_template("register.html")
    else:
        return render_template("register.html")


#  LOGIN PAGE
@app.route("/login", methods=["POST", "GET"])
def login():
    # Submitted the login form
    if request.method == "POST":
        # Get user/password from the form
        user = request.form['name']
        password = request.form['pass']
        # Is the password correct? Is the user valid?
        # If the user isn't valid, it throws an error.
        try:
            if str(database.get("users", "password", f'username="{user}"')[0]) != password:
                flash("Either the name, or the password are wrong.")
                return render_template("login.html")
            else:
                session['user'] = user
                session['is_admin'] = user == database.admin
                # Login successful, redirect to /
                return redirect("/")
        except Exception as e:
            log("Either the name, or the password are wrong.", e, _type="[ERROR]")
            flash("Either the name, or the password are wrong.")
            return render_template("login.html")
    else:
        return render_template("login.html")


@app.route('/logout')
def logout():
    try:
        del connected_members[session['user']]
        session.pop("user", None)
        flash("You have been logged out.", "info")
    except:
        flash("An error has occured.", "info")
    return redirect(url_for("login"))


"""
====================================================
"""


def get_party_chat_id(user: str) -> int:
    if get_party_leader(user):
        return parties[get_party_leader(user)]["chat_id"]
    else:
        return -1


def send_message_to_party(member: str, message: str, author: str = "(System)") -> None:
    chat_id = get_party_chat_id(member)
    chat_rooms[chat_id]["history"].append({"message": message, "author": author})
    emit_to_party(member, event_name="message",
                  message={"id": chat_id, "message": message, "author": author})


def parse_action(command: str) -> None:
    args = command.split("/")
    command_name = args[0]
    if command_name == "accept_friend_request":
        requester = args[1]
        database.make_friends(requester, session["user"])
        # user_data[session['user']]["friends"].append(requester)
        database.send_message(title=f"You and {session['user']} are now friends!",
                              desc=f"{session['user']} has accepted your friend request.",
                              message_sender=session["user"], receiver=request, messagetype="ignore",
                              action="ignore")
        # db['ex'].add_notif(requester)

        # emit_to(requester, 'notif', '/', 'notification!')

    if command_name == "join_party":
        party_owner = args[1]

        if party_owner not in connected_members:
            return

        if party_owner in parties:
            if session['user'] in parties[party_owner]["members"]:
                log(session['user'], "already in party", party_owner)
                return

        # they have no party
        if connected_members[party_owner]["party"] is None:
            create_party(party_owner)

        join_party(party_owner, session['user'])

        emit_to_party(party_owner, event_name="update_party_members", message=get_party_members(party_owner))

        send_message_to_party(party_owner, message=f'{session["user"]} joined!')
        database.add_admin_message(type="u_join", title=f'{session["user"]} joined {party_owner}',
                                   message=f'{session["user"]} joined {party_owner}',
                                   time=strftime("%Y-%m-%d %H:%M:%S", gmtime()))

    if command_name == "accept_suggestion":
        try:
            party_owner = \
                [owner for owner in party_suggestions if session['user'] in party_suggestions[owner]["total"]][0]
            if len(get_party_members(party_owner)) == 0:
                create_party(session['user'])
                if party_owner != session['user']:
                    # copy over the data
                    party_suggestions[session['user']] = party_suggestions[party_owner].copy()
                    # delete old data
                    del party_suggestions[party_owner]
                    party_owner = session['user']

                # make session user the first user in the list
                members = party_suggestions[session['user']]["total"]
                # remove user
                members.remove(session['user'])
                # add user in the beginning
                members = [session['user']] + members
                # update dictionary
                party_suggestions[session['user']]["total"] = members

            else:
                # just join the party lol
                join_party(party_owner, session['user'])

            # append you to the people who accepted the suggestion
            PSP = party_suggestions[party_owner]
            PSP["accepted"].append(session['user'])
            emit_to_party(party_owner, event_name="update_party_members", message=get_party_members(party_owner))
            # if everyone reacted to it, we don't need it anymore woo
            if len(PSP["accepted"]) + len(PSP["rejected"]) == len(PSP["total"]):
                del party_suggestions[party_owner]

            send_message_to_party(party_owner, message=f'{session["user"]} joined!')
            database.add_admin_message(type="u_join", title=f'{session["user"]} joined {party_owner}',
                                       message=f'{session["user"]} joined {party_owner}s party. '
                                               f'This was a K-MEANS suggestion',
                                       time=strftime("%Y-%m-%d %H:%M:%S", gmtime()))
        except IndexError:
            log('lol sucks for u', _type="[???]")

    if command_name == "decline_group_suggestion" or command_name == "decline_group_invite":
        try:
            party_owner = \
                [owner for owner in party_suggestions if session['user'] in party_suggestions[owner]["total"]][0]
            message = f'{session["user"]} was invited to join {party_owner}s party and declined.',

            message += " this was a KNN suggestion." if command_name == "decline_group_suggestion" else \
                " this was a group invite."

            send_message_to_party(party_owner, message=f'{session["user"]} declined.')
            database.add_admin_message(type="u_decline", title=f"{session['user']} did not join {party_owner}'s party",
                                       message=message,
                                       time=strftime("%Y-%m-%d %H:%M:%S", gmtime()))
        except IndexError:
            pass


def send_path_to_party(user_to_track: str) -> None:
    party_members = get_party_members(user_to_track)
    party_leader = get_party_leader(user_to_track)
    if len(party_members) == 0:
        return
    # "destination_status": "No Destination" | "Have Destination" | "Reached Destination"
    paths = []
    if parties[party_leader]["destination_status"] in ["No Destination"]:
        return

    log(f"tracc {user_to_track}, {party_members}")
    done = False

    if len(parties[party_leader]["arrived"]) == len(party_members):
        done = True

    """ done = True
    # meters = 5"""
    for member in party_members:
        if member in connected_members:
            try:
                a = connected_members[member]['current_path']
                path, index = a["path"], a["index"]

                # this still doesn't work

                current_lat, current_lng = connected_members[member]['loc']
                path_and_current_loc = [[current_lat, current_lng]] + path[index:]
                log(f"123, {len(path_and_current_loc)}", index, f"{len(path[index:])}")
                # this works
                # path_and_current_loc = path[index:]

                current_user_path = [{'lat': x[0], 'lng': x[1]} for x in path_and_current_loc]
                paths.append((member, current_user_path))
                """ min_distance = meters * 0.0000089  # convert to lng/lat scale
                 if distance(connected_members[member]['loc'], path[index]) < min_distance:
                     done = False"""

                log(f"Adding path from {member}[:{index}], sending to {user_to_track} ({party_members})")
            except Exception as e:
                log(f"Error in drawing path from {member} on {session['user']}'s screen | {e}", _type="[ERROR]")

    emit_to(user_to_track, 'user_paths', message=paths)
    emit_to("Admin", 'user_paths', message=paths)

    # all the paths are dones
    if done and len(party_members) > 1 and parties[party_leader]["destination_status"] != "Reached Destination":
        parties[party_leader]["destination_status"] = "Reached Destination"
        # online party members in order
        list_of_priorities = [x for x in party_members if x in connected_members]
        database.send_message(title=f"Party Reached Destination",
                              desc=f"{party_leader}'s party has reached their destination.",
                              sender="[System]", receiver="Admin", messagetype="ignore",
                              action=None)


def join_party(owner: str, username: str) -> None:
    if username in parties[owner]["members"]:
        return
    connected_members[username]["party"] = owner
    parties[owner]["members"].append(username)

    party_chat_id = parties[owner]["chat_id"]
    chat_rooms[party_chat_id]["members"][username] = False

    parties[owner]["place_type"] = kmeans.find_best_category(parties[owner]["members"], category_values)
    party_coords(owner)

    connected_members[username]["chats"].append(party_chat_id)

    room = {"id": party_chat_id, **chat_rooms[party_chat_id]}
    emit_to(session['user'], event_name="create_chat", message=room)

    members = parties[owner]["members"]
    for member in members:
        if member in connected_members:
            lat, lng = connected_members[member]["loc"]
            emit_to("Admin", 'my_location_from_server', message={
                "name": member,
                "lat": lat, "lng": lng
            })
    if parties[owner]["destination"]:
        lat, lng = parties[owner]["destination"]
        emit_to(username, event_name='update_destination',
                message={"lat": lat, "lng": lng})

    database.add_admin_message(type="p_sug", title=f"{session['user']} joined {owner}",
                               message=f"{session['user']} joined {owner}'s party.",
                               time=strftime("%Y-%m-%d %H:%M:%S", gmtime()))


def broadcast_user_difference() -> None:
    # friends = database.get_friends(username)
    visible_users = [x for x in connected_members if x != "Admin"]
    # online_friends, offline_friends = [], []

    # def filter_online(username):
    #     if username in visible_users:
    #         online_friends.append(username)
    #     else:
    #         offline_friends.append(username)
    #
    # for user in friends:
    #     filter_online(user)
    #
    # friend_data = {'online': online_friends,
    #                'offline': offline_friends}
    #
    # emit_to(username, 'friend_data', message=friend_data)
    emit_to_everyone(event_name='user_diff', message=visible_users)

    emit_to("Admin", "all_users", message={u: u in connected_members for u in database.get_all_names()})

    log("Last ping data:")
    log("\n".join([f"{name}, {int(time()) - connected_members[name]['last ping']}" for name in visible_users]))
    log({'amount': len(connected_members.keys()), 'names': [user for user in connected_members]})


"""
           SOCKETIO   ENDPOINTS
"""


@socketio.on('yes_i_got_my_loc', namespace='/')
def confirm_loc():
    try:
        connected_members[session['user']]['confirmed_location'] = True
    except KeyError:
        pass


@socketio.on('connect', namespace='/')
def logged_on_users():
    if session['user'] not in members:
        members[session['user']] = {
            "sid": request.sid,  # the socket sid
            "loc": database.get_user_location(session['user']),  # [0, 0],
            "current_path": {"path": [], "index": 0},
            "party": None,  # (party owner's name | None) ,
            "last ping": time_now(),
            "chats": ["0"],  # 0 is the global chat
            "confirmed_location": False
        }
    else:
        log("RECONNECTED", session['user'], session['user'] in connected_members)

        # Reconnecting
        members[session['user']]["sid"] = request.sid
        members[session['user']]["last ping"]: time_now()
        members[session['user']]["confirmed_location"] = False

    # put userdata in the connected member dictionary
    # will be deleted when user is disconnected
    connected_members[session['user']] = members[session['user']]

    # chat ids that the user can see
    chat_ids = [room["id"] for room
                in get_all_user_chats(session['user'])]

    for chat_id in chat_ids:
        # The user needs to create all of his channels again
        # Make it so all the user's channels aren't confirmed
        chat_rooms[chat_id]["members"][session['user']] = False

    if session['user'] != "Admin":
        lat, lng = connected_members[session['user']]["loc"]
        emit_to(session['user'], 'my_location_from_server', message={
            "name": session['user'],
            "lat": lat, "lng": lng
        })


@socketio.on('path_from_user', namespace='/')
def return_path(data):
    # # # # # # # # # # # # # # # # # # # # # # # # # # #.data, step_index
    connected_members[session['user']]['current_path'] = {"path": data, "index": 0}
    log(f"Received path from {session['user']}")
    send_path_to_party(user_to_track=session['user'])


@socketio.on('suggest_location', namespace='/')
def check_ping(data):
    start_vote_on_place(leader=get_party_leader(session['user']),
                        location_data=data)


@socketio.on('ping', namespace='/')
def check_ping(online_users):
    emit_to(session['user'], event_name="ping_reply", message=float(time()))

    """
    We will need to do a few actions for every user.
    1: Check if they are still online. If they are not, 
       remove them.
    2: Send them all of the data they need. This includes:
       NORMAL USER:
          current party users, location, 
          paths, chat tabs and history, 
          online friends, current users
       ADMIN: 
          all online users, locations,
          paths
    """

    # update last pinged time for user

    # idfk is going on here. this shouldn't ever happen
    # but it does
    if session['user'] not in connected_members:
        log("Logged in in ping event")
        logged_on_users()

    members[session['user']] = connected_members[session['user']].copy()

    connected_members[session['user']]["last ping"] = time_now()

    # If user has a party, send them the party coords.
    # Even if the party is currently running a simulation,
    # this shouldn't disturb it.

    messages = database.get_messages(user=session['user'])

    emit_to(session['user'], event_name="inbox_update", message=messages)

    # The ADMIN client doesn't need to see chats

    def client_has_confirmed(chat_id):
        try:
            return chat_rooms[chat_id]["members"][session['user']]
        except KeyError:
            return True

    if session['user'] != "Admin":

        # CREATE CHATS that have not yet been confirmed by the client
        # run over all chats user should have, and check if they've been
        # confirmed.
        [emit_to(session['user'], "create_chat", message=room)
         for room in get_all_user_chats(session['user'])
         if not client_has_confirmed(room["id"])]

        # DELETE CHATS that need to be deleted, them remove them from
        # the deletion queue. repeats until confirmed by user.
        if session['user'] in delete_chats_queue:
            [emit_to(session['user'], event_name="del_chat", message=chat_id)
             for chat_id
             in delete_chats_queue[session['user']]]

        lat, lng = connected_members[session['user']]["loc"]
        emit_to("Admin", 'my_location_from_server', message={
            "name": session['user'],
            "lat": lat, "lng": lng
        })

    else:
        data = separate_into_colours(list(parties.keys()))
        emit_to("Admin", event_name="user_colors", message=data)
        emit_to("Admin", event_name="history_update", message=database.get_history())


@socketio.on('invite_user', namespace='/')
def invite_user(receiver):
    log("inviting", receiver)
    if receiver == session['user']:
        return

    database.send_message(title=f"Party invite from {session['user']}!",
                          desc=f"{session['user']} has invited you to join their party, wanna hang out?",
                          sender=session["user"], receiver=receiver, messagetype="question",
                          action=f"join_party/{session['user']}")

    database.add_admin_message(type="p_sug", title=f"{session['user']} invited {receiver}",
                               message=f"{session['user']} has sent a party invite to {receiver} through the mail",
                               time=strftime("%Y-%m-%d %H:%M:%S", gmtime()))


@socketio.on('add_location', namespace='/')
def add_location_func(data):
    name, lat, lng, loc_type = data.split(", ")
    database.add_location(name, lat, lng, loc_type)
    [send_user_added_locations(online_user) for online_user in connected_members]


@socketio.on('chat_message', namespace='/')
def chat_message(data):
    """
    Multicast message from user to
    appropriate chat
    """
    room, message, author = data["room"], data["message"], session['user']
    chat_rooms[room]["history"].append({"message": message, "author": author})
    room_members = list(chat_rooms[room]["members"].keys())

    for member in room_members:
        emit_to(member, 'message', message={
            "id": room,
            "author": author,
            "message": message
        })
    if message[0] == "/":
        # pass
        parse_chat_command(message, room)


@socketio.on('inbox_notification_react', namespace='/')
def notification_parse(data):
    message_id, reaction = data["message_id"], data["reaction"]

    # first grab the message to see what we need to do with it
    try:
        _id, title, content, sender, receiver, msg_type, action = \
            database.get('messages', '*', f'id={message_id}', first=False)[0]
    except IndexError:
        return
    log(f"{reaction}: {title} | {msg_type}")
    if reaction != "mark_as_read":
        parse_action(action)
    database.remove("messages", f'id={message_id}')

    session['inbox_messages'] = get_messages(session['user'])


@socketio.on('user_added_locations_get', namespace='/')
def get_user_added_loc():
    data = [(name, [float(value) for value in latlng.split(", ")])
            for name, latlng, type in database.get_user_added_locations()]
    emit_to(user=session["user"], event_name='user_added_locations', message=data)


@socketio.on('party_members_list_get', namespace='/')
def emit_party_members():
    emit_to(user=session['user'], event_name="party_members_list_get",
            message=get_party_members(session['user']))


@socketio.on('online_members_get', namespace='/')
def get_online_memb():
    emit_to(user=session['user'], event_name="online_members_get",
            message=[x for x in connected_members if x != "Admin"])


@socketio.on('get_destination', namespace='/')
def get_destination():
    if session['user'] == "Admin":
        return
    if connected_members[session['user']]["party"] is None:
        return
    if parties[get_party_leader(session['user'])]["destination"] is None:
        return

    lat, lng = parties[get_party_leader(session['user'])]["destination"]
    emit_to(session['user'], event_name='update_destination',
            message={"lat": lat, "lng": lng})


@socketio.on('get_coords_of_party', namespace='/')
def get_coords_of_party():
    leader = get_party_leader(session['user'])
    party_coords(leader)


@socketio.on('confirm_chat', namespace='/')
def confirm_chat(chat_id):
    chat_rooms[chat_id]["members"][session['user']] = True


@socketio.on('confirm_del_chat', namespace='/')
def confirm_delete_chat(chat_id):
    try:
        delete_chats_queue[session['user']].remove(chat_id)
    except KeyError:
        pass


@socketio.on('my_location_from_user', namespace='/')
def my_location(data):
    # set_user_location(session['user'], data[0], data[1])
    if "index" in data:
        connected_members[session['user']]['current_path']["index"] = data["index"]
    connected_members[session['user']]['loc'] = data["lat"], data["lng"]
    lat, lng = data["lat"], data["lng"]
    location_obj = {
        "name": session['user'],
        "lat": lat, "lng": lng
    }

    emit_to("Admin", event_name='my_location_from_server', message=location_obj)
    emit_to_party(session['user'], event_name='my_location_from_server', message=location_obj)
    send_path_to_party(session['user'])


@socketio.on('arrived', namespace='/')
def arrived():
    leader = get_party_leader(session['user'])
    if session['user'] not in parties[leader]["arrived"]:
        parties[leader]["arrived"].append(session['user'])

    database.add_admin_message(type="u_arr", title=f"User arrived",
                               message=f"{session['user']} has arrived at {parties[leader]['destination']}",
                               time=strftime("%Y-%m-%d %H:%M:%S", gmtime()))


@socketio.on('start_grouping_users', namespace="/")
def suggest_admin_event():
    """
        ============================= K MEANS =============================
         Get all users that are online,
         not in a group, and have not
         received a suggestion from the server
         (have an active suggestion)"""

    def group_suggestion_filter(u):
        # Check if user is in a suggestion list
        for leader in party_suggestions:
            if u in party_suggestions[leader]["total"]:
                return False
        # If user has a party return false
        leader = get_party_leader(u)
        if leader is not None or leader == "Admin":
            return False
        # Return true, user fits qualifications
        return True

    dont_have_suggestions = filter_dict(d=connected_members, f=group_suggestion_filter)
    if len(dont_have_suggestions) > 1:

        suggestion_groups = kmeans.find_optimal_clusters(
            reps=100,
            only_these_values=filter_dict(kmeans.values, lambda x: x in dont_have_suggestions),
            verbose=False
        )
        for center in suggestion_groups:
            names = [person[0] for person in suggestion_groups[center]]

            suggest_party(names)


@socketio.on('request_destination_update', namespace='/')
def destination_update_request(data):
    start_vote_on_place(get_party_leader(session['user']), data, add_marker=False)


@socketio.on('confirm_message', namespace='/')
def confirm_message(message_id):
    pass
    # message_ids[message_id]["confirmed"] = True


@socketio.on('disconnect', namespace='/')
def disconnect_event():
    try:
        if get_party_leader(session['user']) is not None:
            emit_to_party(session['user'], event_name="user_colors", message=["gray", session['user']])
        connected_members.pop(session['user'])
    except KeyError:
        pass


def keep_sending_user_diff():
    global app
    with app.app_context():
        while 1:
            try:
                sleep(1)
                broadcast = False
                for username in connected_members.copy():
                    broadcast = True
                    log("sending data to", username)
                    if not connected_members[username]["confirmed_location"] and username != "Admin":
                        lat, lng = connected_members[username]["loc"]
                        emit_to(username, 'my_location_from_server', message={
                            "name": username,
                            "lat": lat, "lng": lng
                        })

                    if time_now() - connected_members[username]["last ping"] > 2:
                        log(f"DELETING {username}")
                        del connected_members[username]

                    emit_to(user=username, event_name="party_members_list_get",
                            message=get_party_members(username))

                    # if get_party_members(username):
                    party_coords(username)
                    send_path_to_party(username)

                    if username == "Admin":
                        best_3 = sorted(list(popular_places.keys()), key=lambda x: popular_places[x])[-3:]
                        emit_to("Admin", event_name="popular_places", message=best_3)

                if broadcast:
                    broadcast_user_difference()

            except Exception as e:
                log(e, _type="[ERROR]")


user_diff_thread = Thread(target=keep_sending_user_diff)
user_diff_thread.deamon = True
user_diff_thread.start()
socketio.run(app, host="0.0.0.0", port=8080)
