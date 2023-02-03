from flask import Flask, request, jsonify
from flask_cors import CORS
from blueprints.sse_blueprint import sse
from apscheduler.schedulers.background import BackgroundScheduler
from token_required import token_required

import discord
import logging

discord.utils.setup_logging(level=logging.INFO, root=True)
logging.getLogger("apscheduler.executors.default").setLevel(logging.ERROR)

app = Flask(__name__)
app.config["REDIS_URL"] = "redis://192.168.2.201"
app.register_blueprint(sse, url_prefix="/stream")

CORS(app, resources={"/stream": {"origins": "*"}})

last_published = {}
PREDICTIONS_CHANNEL = "predictions"
SUBS_CHANNEL = "subs"

# User responses to current active poll
POLL_ANSWERS_CHANNEL = "poll-answers"

# New poll information
POLLS_CHANNEL = "polls"


def keep_alive():
    with app.app_context():
        sse.publish("\n\n", type="keepalive", channel=PREDICTIONS_CHANNEL)
        sse.publish("\n\n", type="keepalive", channel=SUBS_CHANNEL)
        sse.publish("\n\n", type="keepalive", channel=POLL_ANSWERS_CHANNEL)
        sse.publish("\n\n", type="keepalive", channel=POLLS_CHANNEL)


sched = BackgroundScheduler(daemon=True)
sched.add_job(keep_alive, "interval", seconds=15)
sched.start()


@app.route("/")
def index():
    return jsonify(last_published)


@app.route("/publish-poll", methods=["POST"])
@token_required
def publish_poll():
    try:
        to_publish = parse_poll_answer_from_request()
        sse.publish(to_publish, type="publish", channel=POLL_ANSWERS_CHANNEL)
        return ("OK", 200)
    except (KeyError, ValueError):
        return ("Bad Request", 400)

@app.route("/publish-poll-answer", methods=["POST"])
@token_required
def publish_poll_answer():
    try:
        to_publish = parse_poll_from_request()
        sse.publish(to_publish, type="publish", channel=POLLS_CHANNEL)
        return ("OK", 200)
    except (KeyError, ValueError):
        return ("Bad Request", 400)

@app.route("/publish-prediction", methods=["POST"])
@token_required
def publish_prediction():
    global last_published
    try:
        to_publish = parse_prediction_from_request()
        sse.publish(to_publish, type="publish", channel=PREDICTIONS_CHANNEL)
        last_published = to_publish
        return ("OK", 200)
    except (KeyError, ValueError):
        return ("Bad Request", 400)


@app.route("/publish-sub", methods=["POST"])
@token_required
def publish_sub():
    try:
        to_publish = parse_sub_from_request()
        sse.publish(to_publish, type="publish", channel=SUBS_CHANNEL)
        return ("OK", 200)
    except (KeyError, ValueError):
        return ("Bad Request", 400)


def parse_prediction_from_request():
    description = request.json["description"]
    option_one = request.json["optionOne"]
    option_two = request.json["optionTwo"]
    option_one_points = int(request.json["optionOnePoints"])
    option_two_points = int(request.json["optionTwoPoints"])
    end_time = request.json["endTime"]
    accepting_entries = request.json["acceptingEntries"]
    ended = request.json["ended"]

    return {
        "description": description,
        "optionOne": option_one,
        "optionTwo": option_two,
        "optionOnePoints": option_one_points,
        "optionTwoPoints": option_two_points,
        "endTime": end_time,
        "acceptingEntries": accepting_entries,
        "ended": ended,
    }


def parse_sub_from_request():
    name = request.json["name"]
    tier = request.json["tier"]
    message = request.json["message"]
    return {"name": name, "tier": tier, "message": message}

def parse_poll_from_request():
    """
    {
        "title": "This is a sample poll",
        "options": [
            "Sample text",
            "123",
            "another option",
            "these are options"
        ]
    }
    """
    title = request.json["title"]
    options = request.json["options"]
    return {"title": title, "options": options}

def parse_poll_answer_from_request():
    """
    Option Number is 1-indexed
    {
        "userID": 12938123,
        "optionNumber": 1,
        "userRoleIDs": [123, 823, 231, 293]
    }
    """
    user_id = request.json["userID"]
    option_number = request.json["optionNumber"]
    user_roles = request.json["userRoleIDs"]
    return {"userID": user_id, "optionNumber": option_number, "userRoleIDs": user_roles}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3000)
