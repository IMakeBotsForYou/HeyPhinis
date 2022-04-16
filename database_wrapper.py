import sqlite3
import json
import threading


def st2int(array):
    """
    :param array: An array of objects(strings) that can be converted to ints
    :return: An array of ints
    """
    return [int(x) for x in array]


def int2st(array):
    """
    :param array: An array of ints
    :return: The array but converted into strings
    """
    return [str(x) for x in array]


def smallest_free(array):
    """
    :param array: An array of integers
    :return: The lowest "free" integer.
    E.g:
    <- [1, 3, 4]
    -> 2

    <- [1, 2, 3]
    -> 4

    <- [2, 3]
    -> 1
    """
    lowest = 1
    if not array:
        return 1
    m = min(array)
    if m != 1:
        return 1
    for i, value in enumerate(array[1:]):
        if value - lowest == 1:
            lowest = value
        else:
            return lowest + 1
    return lowest


def reformat(*args):
    """
    :param args: The variables that we want to convert into an SQL-usable string
    :return: formated string (var1, var2, var
    3..) for SQL purposes
    """
    st = "("
    variables = [i for i in args]
    need_trim = True
    for var in variables:
        # Loop over variables
        # Convert int
        if isinstance(var, int):
            st += f'{var}, '
            need_trim = True
        # Convert list by adding " " and ,
        elif isinstance(var, list):
            st += '"' + ", ".join([str(x) for x in var]) + '"'
            need_trim = False
        else:
            # Neither an int nor an array, need trimming
            st += f'"{var}", '
            need_trim = True

    if need_trim:
        return st[:-2] + ")"
    else:
        return st + ")"


class Database:
    """
    A class to interact with an SQL database
    """
    def __init__(self, path):
        self.lock = threading.Lock()
        self.path = path.split(".")[0] + '.db'
        self.data = sqlite3.connect(self.path, check_same_thread=False)
        self.cursor = self.data.cursor()

    def get(self, table, column, condition=None, limit=None, first=True):
        """
        :param table: database table
        :param column: What column?
        :param condition: condition of search
        :param limit: Limit the search to X results
        :param first: Return first of every result
        :return: The results
        """

        s = f"SELECT {column} FROM {table}"
        if condition: s += f" WHERE {condition}"
        if limit: s += f" LIMIT {limit}"
        return [x[0] if first else x for x in self.execute(s)]

    def execute(self, line, fetch=None):
        """
        :param line: SQL command
        :param fetch: Number to of results to return
        :return: The results
        """
        ret = None
        try:
            self.lock.acquire(True)

            self.cursor.execute(line)
            if not fetch or fetch == -1:
                ret = self.cursor.fetchall()
                self.data.commit()

            else:
                ret = self.cursor.fetchmany(fetch)
                self.data.commit()
            # do something
        finally:
            self.lock.release()
            if ret is None:
                print(f"Returning None, {line}")
            return ret

    def fix_seq(self):
        # columns = ["users"]
        # for na in columns:
        #     a = self.get(na, "id")
        #     self.edit("sqlite_sequence", "seq", smallest_free(a) if a else 0, f'name="{na}"')
        pass

    def add(self, table, values):
        """
        :param table: Table in the SQL
        :param values: Values to add (if multiple, then as a tuple)
        :return: None
        """
        self.fix_seq()
        print(F"INSERT INTO {table} VALUES {values}")
        self.execute(F"INSERT INTO {table} VALUES {values}")
        self.fix_seq()
        # except Exception as e:
        #     print(1, e)
        self.data.commit()

    def remove(self, table, condition=None):
        """
        :param table: Table in SQL
        :param condition: Condition for the item (E.g. 'name="foo"')
        :return:
        """
        self.execute(f'DELETE FROM {table} WHERE {"1=1" if not condition else condition}')
        self.fix_seq()

    def edit(self, table, column, newvalue, condition=None):
        s = f'UPDATE {table} SET {column} = "{newvalue}"'
        s += f" WHERE {condition}" if condition else " WHERE 1=1"
        self.execute(s)


class UserData(Database):
    """
        Database of users
    """
    def __init__(self, path):
        super().__init__(path)
        # Define admin user
        self.admin = "Admin"
        self.parties = []
        with open('static/js/users.js', 'w') as f:
            f.write(f'var users = {json.dumps(self.get("users", "username"))}')

    def get_all_names(self, remove_admin=False):
        """
        :param remove_admin: Get all regular users
        :return: Array of str
        """
        if remove_admin:
            return [name for name in self.get("users", "username") if name != "Admin"]

        return self.get("users", "username")

    def send_message(self, title, desc, sender, receiver, messagetype, action):
        """
        :param title: Title of message
        :param desc: description/body of message
        :param sender: Sender
        :param receiver: Receiver
        :param messagetype: Question/Normal/Suggestion ect...
        :param action: Action for the parser function to run when message accepted/ignored
        :return: None
        """
        print("added", title, desc)
        self.add("messages (title, content, sender, receiver, type, action)",
                 reformat(title, desc, sender, receiver, messagetype, action))

    def get_user_data(self, colum=None):
        """
        :param colum: Specify a column in the SQL to get, if left empty will return all columns
        :return: All the user data
        """
        return self.get("users", colum if colum else "*", first=colum is not None)

    def fix_seq(self):
        """
        When deleting things like messsages,
        the sequence number gets really high.
        This function fixes it, bringing it back down
        to the lowest free integer.
        :return: None
        """
        columns = ["users", "messages"]
        for na in columns:
            a = self.get(na, "id")
            self.edit("sqlite_sequence", "seq", smallest_free(a) if a else 0, f'name="{na}"')

    def get_user_location(self, username):
        """
        :param username: Username of whose location to fetch
        :return: [float(lat), float(lng)]
        """
        if username == "Admin":
            return None
        return [float(value) for value in self.get("users", "loc", condition=f'username="{username}"')[0].split(", ")]

    def set_user_location(self, username, newvalue):
        """
        :param username: Username to update location
        :param newvalue: Newvalue of location
        :return: None
        """
        self.edit('users', 'loc', newvalue=newvalue, condition=f'username="{username}"')

    def create_party(self, user):
        """
        Creates an empty party with user, deleting any previous party they had.
        :param user: Leader/Creator of party
        :return: None
        """
        if len(self.get('parties', 'creator', condition=f'creator="{user}"')) > 0:
            for member in self.get_party_members(user):
                print('removing', member)
                self.remove_from_party(user, member)
            self.remove('parties', condition=f'creator="{user}"')

        self.add('parties', reformat(user, "", "no current request"))
        self.add_to_party(user, user)

    def set_party_status(self, creator, newvalue):
        """
        :param creator: Creator of party
        :param newvalue: New status
        :return: None
        """
        self.edit('parties', 'status', newvalue=newvalue, condition=f'creator="{creator}"')

    def get_party_status(self, creator):
        """
        :param creator: Creator of party
        :return: Status of party (str)
        """
        data = self.get('parties', 'status', condition=f'creator="{creator}"', first=False)
        if len(data) == 0:
            return "No Party"
        else:
            return data[0]

    def reset_notifs(self, user):
        """
        :param user: User to reset
        :return: None
        """
        return self.edit("users", "notifications", newvalue=0, condition=f'username="{user}"')

    def add_notif(self, user):
        """
        :param user: User to add notif to
        :return: Amount of new notifications
        """
        num = self.get_notifs(user)
        self.edit("users", "notifications", newvalue=num+1, condition=f'username="{user}"')
        return num+1

    def get_notifs(self, user):
        """
        :param user: User to fetch
        :return: amount of notifications user has
        """
        return int(self.get("users", "notifications", condition=f'username="{user}"')[0])

    def add_to_party(self, owner, user_to_add):
        """
        :param owner: Owner of party
        :param user_to_add: User to add to said party
        :return: None
        """
        members = self.get('parties', 'members', condition=f'creator="{owner}"')
        if len(members) == 0:
            members = []
        else:
            members = members[0].split(", ")
        members.append(user_to_add)
        members = list({x for x in [a for a in members if a != ""]})  # remove dupes
        self.edit('parties', 'members', newvalue=", ".join(members), condition=f'creator="{owner}"')
        self.edit('users', 'current_party', newvalue=owner, condition=f'username="{user_to_add}"')

    def remove_from_party(self, owner, user_to_remove):
        """
        :param owner: Owner of party
        :param user_to_remove: User to remove from said party
        :return: None
        """
        members = self.get('parties', 'members', condition=f'creator="{owner}"')[0].split(", ")
        members.remove(user_to_remove)
        self.edit('parties', 'members', newvalue=", ".join(members), condition=f'creator="{owner}"')
        self.edit('users', 'current_party', newvalue="", condition=f'username="{user_to_remove}"')

    def get_party_members(self, owner):
        """
        :param owner: Owner of party
        :return: Get members of owner's party
        """
        a = self.get('parties', 'members', condition=f'creator="{owner}"')
        if len(a) == 0:
            return []
        else:
            a = a[0].split(", ")
            a.remove(owner)
            return [owner] + a

    def get_messages(self, user=None):
        """
        :param user: User to fetch
        :return: All messages to user in json format
        """
        mes = self.get('messages', '*', condition=f'receiver="{user}"' if user else None, first=False)
        ret = {"status": "empty", "messages": {}}
        for message in mes:
            xx, title, content, sender, receiver, m_type, action = message
            ret["status"] = "200"
            if receiver in ret['messages']:
                ret["messages"][receiver].append(
                    {"id": xx,
                     "title": title,
                     "content": content,
                     "sender": sender,
                     "type": m_type,
                     "action": action
                     })
            else:
                ret["messages"][receiver] = \
                    [{"id": xx,
                      "title": title,
                      "content": content,
                      "sender": sender,
                      "type": m_type,
                      "action": action
                      }]
        return ret

    def get_friends(self, user):
        """
        :param user: User to fetch
        :return: All friends of user (array[str])
        """
        f = self.get("users", "friends", condition=f'username="{user}"')
        print(f)
        if len(f) > 0 and f != [None]:
            return f[0].split(', ')
        else:
            return []

    def add_location(self, loc_name, lat, lng, loc_type):
        """
        Add a user-added location to the database
        :param loc_name: Location name
        :param lat: lat coordinate (float)
        :param lng: lng coordinate (float)
        :param loc_type: E.g. Restaurant...
        :return: None
        """
        self.add('user_added_locations (name, latlng, type)', reformat(loc_name, f"{lat}, {lng}", loc_type))

    def add_user(self, username, password, friends="", interests="parks|0|restaurant|0|"):
        """
        Add new user to the database
        :param username: Name
        :param password: Password
        :param friends: Array of strings. No friends initially
        :param interests: Interests of user, default: parks|0|restaurant|0|
        :return: None
        """
        self.add("users (username, password, friends, interests)", reformat(username, password, friends, interests))

        # # # #  # # #  # # #  # # #  # # #  # # #  # # #
        with open('static/js/users.js', 'w') as f:
            f.write(f'var users = {json.dumps(self.get("users", "username"))}')
        # # # #  # # #  # # #  # # #  # # #  # # #  # # #

    def make_friends(self, user1, user2):
        """
        Make two 2 users friends of each other
        :param user1: First uername
        :param user2: Second username
        :return: None
        """
        current_friends1 = self.get("users", "friends", condition=f'name="{user1}"')[0].split(", ")
        current_friends2 = self.get("users", "friends", condition=f'name="{user2}"')[0].split(", ")
        current_friends1.append(user2)
        current_friends2.append(user1)
        self.edit("users", "friends", ", ".join(current_friends1), condition=f'name={user1}')
        self.edit("users", "friends", ", ".join(current_friends2), condition=f'name={user2}')

    def get_user_added_locations(self):
        return self.get('user_added_locations', 'name, latlng, type', first=False)

    def remove_user(self, name):
        """
        :param name: User to delete from the database
        :return: None
        """
        try:
            # if password == self.execute(f'SELECT password FROM users WHERE username="{name}"', 1)[0][0]:
            self.execute(f'DELETE FROM users WHERE username="{name}"')
            # else:
            #     print("Wrong password, you can't do that.")
        except IndexError:
            print(f"User {name} isn't registered!")

        with open('static/js/users.js', 'w') as f:
            f.write(f'var users = {json.dumps(self.get("users", "username"))}')

    def close(self):
        """
        Closes connection with the database
        :return: None
        """
        print("Finished")
        self.data.close()


def reset_locations():
    """
    Resets location of all users to "their houses"
    This is an "Admin User" feature for debuging purposes
    :return: None
    """
    for name in my_db.get_all_names():
        if name == "Admin":
            continue
        my_db.edit("users", "loc",
                   newvalue=def_locations.get("locations", "latlng", condition=f'username="{name}"')[0],
                   condition=f'username="{name}"')


def main():
    global my_db
    global def_locations
    my_db = UserData("database/data")
    def_locations = Database('database/def_locations')
    # for name in my_db.get_all_names():
    #     def_locations.add("locations", reformat(name, my_db.get_user_location(name)))


# my_db.remove_user("Guy", "123")
# print(my_db.get_users())


if __name__ == "__main__":
    main()

    # names = ["Mike", "Manor", "Liza", "Maya", "Yakov"]
    # import random
    # for name in names:
    #     my_db.add_user(name, "123", random.choice(names))
