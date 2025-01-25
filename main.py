"""
Primary file tp run the Flask app.
"""

import os
import urllib.parse
from datetime import datetime

from requests import post, get
from flask import Flask, redirect, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost:5000/callback"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE_URL = "https://api.spotify.com/v1/"


@app.route("/")
def index():
    """
    The main page of the application, which primarily provides a button to login with Spotify credentials.
    """
    return "Welcome to Spotify Organizer <a href='/login'>Login with Spotify</a>"


@app.route("/login")
def login():
    """
    Make a request to Spotify's authorization URL, pass the params and scope to give access, and redirect it.
    """
    scope = "user-read-private user-read-email"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "show_dialog": True,  # omit later once testing is complete
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)


@app.route("/callback")
def callback():
    """
    Handles OAuth2 callback by processing authorization code or error response, exchanges
    code for access token, and stores those tokens (access, refresh) in session for future API usage.
    """
    if "error" in request.args:
        return jsonify({"error": request.args["error"]})

    if "code" in request.args:
        req_body = {
            "code": request.args["code"],
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }

        response = post(TOKEN_URL, data=req_body, timeout=30)
        token_info = response.json()
        session["access_token"] = token_info["access_token"]
        session["refresh_token"] = token_info["refresh_token"]
        session["expires_at"] = (
            datetime.now().timestamp() + token_info["expires_in"]
        )  # typically token expires in 1h (or 3600s)

        # need login to check if the access token has expired so that we can refresh it
        return redirect("/playlists")


def get_auth_header(token):
    """
    Helper Function: Get an authorization header based on the produced token, which is used to
    authenticate and authorize this client to access a resource on the Spotify servers.
    """
    return {"Authorization": "Bearer " + token}


@app.route("/playlists")
def get_playlists():
    """
    Retrieve all playlists from the user.
    """
    if "access_token" not in session:
        return redirect("/login")

    if datetime.now().timestamp() > session["expires_at"]:
        return redirect("/refresh-token")

    response = get(
        API_BASE_URL + "me/playlists",
        headers=get_auth_header(session["access_token"]),
        timeout=30,
    )
    playlists = response.json()
    return playlists


@app.route("/refresh-token")
def refresh():
    """
    Check if access token exists or is expired.
     - If refresh token doesn't exist, then user has not logged in.
     - If access token is expired, then send the refresh token to Spotify in exchange for a new access 
     token for the session.
    """
    if "refresh_token" not in session:
        return redirect("/login")

    if datetime.now().timestamp() > session["expires_at"]:
        req_body = {
            "grant_type": "refresh_token",
            "refresh_token": session["refresh_token"],
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }

        response = post(TOKEN_URL, data=req_body, timeout=30)
        new_token_info = response.json()

        session["access_token"] = new_token_info["access_token"]
        session["expires_at"] = (
            datetime.now().timestamp() + new_token_info["expires_in"]
        )

        return redirect("/playlists")


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
