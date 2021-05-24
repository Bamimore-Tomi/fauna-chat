import hashlib,os
import datetime, pytz
from flask import Flask, render_template, request, flash, redirect, url_for, session, Response
from flask_socketio import SocketIO
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
                    "messages":[],
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
    print(recepient_chats)
    #Check if the chat the users is trying to add has not been added before
    try:
        chat_list = [list(i.values())[0] for i in chats["data"]["chat_list"]]
    except:
        chat_list = []
        
    if new_chat_id["ref"].id() not in chat_list:
        #Append the new chat to the chat list of the user
        room_id = str(int(new_chat_id["ref"].id()) + int(user_id))[-4:]
        chats["data"]["chat_list"].append( { "user_id":new_chat_id["ref"].id(), "room_id":int(room_id) })
        recepient_chats["data"]["chat_list"].append( { "user_id":user_id, "room_id":int(room_id) })

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

    return redirect(url_for("chat"))
@app.route("/chat", methods=["GET","POST"])
def chat():
    chat = client.query(q.get(q.match(q.index("chat_index"), session["user"]["id"] )))
    return render_template("clean_chat.html" , user_data = session["user"])

@socketio.on("outgoing")
def handle_my_custom_event(json, methods=["GET", "POST"]):
    print("received my event: " + str(json))
    socketio.emit("message", json)
if __name__ == "__main__":
    socketio.run(app, debug=True)