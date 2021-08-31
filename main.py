import hashlib, os, time
from functools import wraps
from datetime import datetime
import pytz
from flask import (
    Flask,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    session,
    Response,
)
from flask_socketio import SocketIO, join_room
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient
from dotenv import load_dotenv

load_dotenv()
# Initialize client connection to database
client = FaunaClient(secret=os.getenv("FAUNA_KEY"))
app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = "vnkdjnfjknfl1232#"
# Initialize socketio application
socketio = SocketIO(app)

# Login decorator to ensure user is logged in before accessing certain routes
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


# Index route, this route redirects to login/register page
@app.route("/", methods=["GET", "POST"])
def index():
    return redirect(url_for("login"))


# Register a new user and hash password
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # To setup validator for email
        email = request.form["email"].strip().lower()
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        # Make sure no ther user with similar credentials is already registered
        try:
            user = client.query(q.get(q.match(q.index("users_index"), username)))
            flash("User already exists with that username.")
            return redirect(url_for("login"))
        except:
            user = client.query(
                q.create(
                    q.collection("users"),
                    {
                        "data": {
                            "username": username,
                            "email": email,
                            "password": hashlib.sha512(password.encode()).hexdigest(),
                            "date": datetime.now(pytz.UTC),
                        }
                    },
                )
            )
            # Create a new chat list for newly registered user
            chat = client.query(
                q.create(
                    q.collection("chats"),
                    {
                        "data": {
                            "user_id": user["ref"].id(),
                            "chat_list": [],
                        }
                    },
                )
            )
            flash("Registration successful.")
            return redirect(url_for("login"))
    return render_template("auth.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # To add email validator here
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        try:
            # Query the data base for the inputted email address
            user = client.query(q.get(q.match(q.index("user_index"), email)))
            if (
                hashlib.sha512(password.encode()).hexdigest()
                == user["data"]["password"]
            ):
                # Create new session for newly logged in user
                session["user"] = {
                    "id": user["ref"].id(),
                    "username": user["data"]["username"],
                    "email": user["data"]["email"],
                }
                return redirect(url_for("chat"))
            else:
                raise Exception()
        except Exception as e:
            flash("You have supplied invalid login credentials, please try again!")
            return redirect(url_for("login"))
    return render_template("auth.html")


@app.route("/new-chat", methods=["POST"])
@login_required
def new_chat():
    user_id = session["user"]["id"]
    new_chat = request.form["email"].strip().lower()
    # If user is trying to add their self, do nothing
    if new_chat == session["user"]["email"]:
        return redirect(url_for("chat"))

    try:
        # If user tries to add a chat that has not registerd, do nothing

        new_chat_id = client.query(q.get(q.match(q.index("user_index"), new_chat)))
    except:
        return redirect(url_for("chat"))
    # Get the chats related to both user
    chats = client.query(q.get(q.match(q.index("chat_index"), user_id)))
    recepient_chats = client.query(
        q.get(q.match(q.index("chat_index"), new_chat_id["ref"].id()))
    )
    # Check if the chat the users is trying to add has not been added before
    try:
        chat_list = [list(i.values())[0] for i in chats["data"]["chat_list"]]
    except:
        chat_list = []

    if new_chat_id["ref"].id() not in chat_list:
        # Append the new chat to the chat list of the user
        room_id = str(int(new_chat_id["ref"].id()) + int(user_id))[-4:]
        chats["data"]["chat_list"].append(
            {"user_id": new_chat_id["ref"].id(), "room_id": room_id}
        )
        recepient_chats["data"]["chat_list"].append(
            {"user_id": user_id, "room_id": room_id}
        )

        # Update chat list for both users
        client.query(
            q.update(
                q.ref(q.collection("chats"), chats["ref"].id()),
                {"data": {"chat_list": chats["data"]["chat_list"]}},
            )
        )
        client.query(
            q.update(
                q.ref(q.collection("chats"), recepient_chats["ref"].id()),
                {"data": {"chat_list": recepient_chats["data"]["chat_list"]}},
            )
        )
        client.query(
            q.create(
                q.collection("messages"),
                {"data": {"room_id": room_id, "conversation": []}},
            )
        )

    return redirect(url_for("chat"))


@app.route("/chat/", methods=["GET", "POST"])
@login_required
def chat():
    # Get the room id in the url or set to None
    room_id = request.args.get("rid", None)
    # Initialize context that contains information about the chat room
    data = []
    try:
        # Get the chat list for the user in the room i.e all of the people they have a chat histor with on the application
        chat_list = client.query(
            q.get(q.match(q.index("chat_index"), session["user"]["id"]))
        )["data"]["chat_list"]
    except:
        chat_list = []

    for i in chat_list:
        # Query the database to get the user name of users in a user's chat list
        username = client.query(q.get(q.ref(q.collection("users"), i["user_id"])))[
            "data"
        ]["username"]
        is_active = False
        # If the room id in the url is the same with any of the room id in a user's chat list, that room is currently the active room
        if room_id == i["room_id"]:
            is_active = True
        try:
            # Get the last message for each chat room
            last_message = client.query(
                q.get(q.match(q.index("message_index"), i["room_id"]))
            )["data"]["conversation"][-1]["message"]
        except:
            # Set variable to this when no messages have been sent to the room
            last_message = "This place is empty. No messages ..."
        data.append(
            {
                "username": username,
                "room_id": i["room_id"],
                "is_active": is_active,
                "last_message": last_message,
            }
        )
    # Get all the message history in a certian room
    messages = []
    if room_id != None:
        messages = client.query(q.get(q.match(q.index("message_index"), room_id)))[
            "data"
        ]["conversation"]

    return render_template(
        "chat.html",
        user_data=session["user"],
        room_id=room_id,
        data=data,
        messages=messages,
    )


# Custom time filter to be used in the jinja template
@app.template_filter("ftime")
def ftime(date):
    return datetime.fromtimestamp(int(date)).strftime("%m.%d. %H:%M")


@socketio.on("join-chat")
def join_private_chat(data):
    room = data["rid"]
    join_room(room=room)
    socketio.emit(
        "joined-chat",
        {"msg": f"{room} is now online."},
        room=room,
        # include_self=False,
    )


@socketio.on("outgoing")
def chatting_event(json, methods=["GET", "POST"]):
    room_id = json["rid"]
    timestamp = json["timestamp"]
    message = json["message"]
    sender_id = json["sender_id"]
    sender_username = json["sender_username"]

    messages = client.query(q.get(q.match(q.index("message_index"), room_id)))
    conversation = messages["data"]["conversation"]
    conversation.append(
        {
            "timestamp": timestamp,
            "sender_username": sender_username,
            "sender_id": sender_id,
            "message": message,
        }
    )
    client.query(
        q.update(
            q.ref(q.collection("messages"), messages["ref"].id()),
            {"data": {"conversation": conversation}},
        )
    )
    socketio.emit(
        "message",
        json,
        room=room_id,
        include_self=False,
    )


if __name__ == "__main__":
    socketio.run(app, debug=True)
