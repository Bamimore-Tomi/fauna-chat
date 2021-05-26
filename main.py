import hashlib,os,time
import datetime, pytz
from flask import Flask, render_template, request, flash, redirect, url_for, session, Response
from flask_socketio import SocketIO, join_room
from faunadb import query as q
from faunadb.objects import Ref
from faunadb.client import FaunaClient
from dotenv import load_dotenv
load_dotenv()

client = FaunaClient(secret=os.getenv("FAUNA_KEY"))
app = Flask(__name__)
app.config["SECRET_KEY"] = "vnkdjnfjknfl1232#"
socketio = SocketIO(app)

@app.route("/", methods=["GET","POST"])
def sessions():
    return render_template("chat.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method=="POST":
        email = request.form["email"].strip().lower()
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        try:
           user = client.query(q.get(q.match(q.index("users_index"), username)))
           flash("User already exists with that username.")
           return redirect(url_for("login"))
        except:
            user = client.query(q.create(q.collection("users"), {
                "data": {
                    "username": username,
                    "email": email,
                    "password": hashlib.sha512(password.encode()).hexdigest(),
                    "date": datetime.datetime.now(pytz.UTC)
                }
            }))
            chat = client.query(q.create(q.collection("chats"), {
                "data": {
                    "user_id": user["ref"].id(),
                    "chat_list": [],
                }
            }))
            flash("Registration successful.")
            return redirect(url_for("login"))
    return render_template("auth.html")

@app.route("/login",methods=["GET","POST"])
def login():
   if request.method == "POST":
       email = request.form["email"].strip().lower()
       password = request.form["password"]

       try:
           user = client.query(q.get(q.match(q.index("user_index"),email )))
           print(user)
           if hashlib.sha512(password.encode()).hexdigest() == user["data"]["password"]:
               session["user"] = {
                   "id": user["ref"].id(),
                   "username": user["data"]["username"],
                   "email":user["data"]["email"]
               }
               return redirect(url_for("chat"))
           else:
               raise Exception()
       except Exception as e:
           print(e)
           flash("You have supplied invalid login credentials, please try again!")
           return redirect(url_for("login"))
   return render_template("auth.html")

@app.route("/new-chat", methods=["POST"])
def new_chat():
    user_id =  session["user"]["id"]
    new_chat = request.form["email"].strip().lower()
    #If user is trying to add theirself, do nothing
    if new_chat == session["user"]["email"]:
        return redirect(url_for("chat"))

    try:
        #If user trys to add a chat that has not registerd, do nothing

        new_chat_id = client.query(q.get(q.match(q.index("user_index"),new_chat )))
    except: 
        return redirect(url_for("chat"))
    #Get the chats related to both user
    chats = client.query(q.get(q.match(q.index("chat_index"),user_id )))
    recepient_chats = client.query(q.get(q.match(q.index("chat_index"),new_chat_id["ref"].id() )))
    #Check if the chat the users is trying to add has not been added before
    try:
        chat_list = [list(i.values())[0] for i in chats["data"]["chat_list"]]
    except:
        chat_list = []

    if new_chat_id["ref"].id() not in chat_list:
        #Append the new chat to the chat list of the user
        room_id = str(int(new_chat_id["ref"].id()) + int(user_id))[-4:]
        chats["data"]["chat_list"].append( { "user_id":new_chat_id["ref"].id(), "room_id":room_id })
        recepient_chats["data"]["chat_list"].append( { "user_id":user_id, "room_id":room_id })
        
        #Update chat list for both users
        client.query(q.update(
            q.ref(
                q.collection("chats"), chats["ref"].id()), 
                {"data": {
                    "chat_list":chats["data"]["chat_list"] }}
                ))
        client.query(q.update(
            q.ref(
                q.collection("chats"), recepient_chats["ref"].id()), 
                {"data": {
                    "chat_list":recepient_chats["data"]["chat_list"] }}
                ))
        client.query(q.create(q.collection("messages"), {
                "data": {
                    "room_id": room_id,
                    "conversation": []
                }
            }))

    return redirect(url_for("chat"))

@app.route("/chat/", methods=["GET","POST"])
def chat():
    room_id = request.args.get("rid", None) 
    data = []
    try:
        chat_list = client.query(q.get(q.match(q.index("chat_index"), session["user"]["id"] )))["data"]["chat_list"]
    except:
        chat_list = []
    messages = []
    if room_id!=None:
        messages = client.query(q.get(q.match(q.index("message_index"),room_id )))["data"]["conversation"]

    print("MESSAGES",messages)
    for i in chat_list:
        username = client.query(q.get(q.ref(q.collection("users"), i["user_id"])))["data"]["username"]
        is_active = False
        if room_id == i["room_id"]:
            is_active = True
        data.append({"username":username, "room_id":i["room_id"],"is_active":is_active })
    return render_template("clean_chat.html" , user_data = session["user"],room_id=room_id, data=data, messages=messages)

@socketio.on("join-chat")
def join_private_chat(data):
    room = data["rid"]
    join_room(room=room)
    socketio.emit(
        "joined-chat",
        {"msg": f"{room} is now online."},
        room=room,
        #include_self=False,
    )


@socketio.on("outgoing")
def handle_my_custom_event(json, methods=["GET", "POST"]):
    room_id = json["rid"]
    timestamp = json["timestamp"]
    message = json["message"]
    sender_id = json["sender_id"]
    sender_username = json["sender_username"]

    messages = client.query(q.get(q.match(q.index("message_index"),room_id )))
    conversation = messages["data"]["conversation"]
    conversation.append({"timestamp":timestamp,"sender_username":sender_user, "sender_id":sender_id, "message":message})
    client.query(q.update(
        q.ref(
            q.collection("messages"), messages["ref"].id()), 
            {"data": {
                "conversation": conversation }}
            ))
    socketio.emit("message", json, room= room_id, include_self=False,)
if __name__ == "__main__":
    socketio.run(app, debug=True)