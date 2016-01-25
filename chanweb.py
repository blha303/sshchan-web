#!/usr/bin/env python3

import re
from flask import *
from requests import post as req_post
from json import load, dump
from subprocess import check_output
from datetime import datetime
from ago import human
from misaka import html
from lxml.html.clean import clean_html
from os import mkdir, getenv
import os.path
import logging
import logging.config

NAME = "Chanweb"
GH_URL = "https://github.com/blha303/sshchan-web"
ROOT = "/home/blha303/sshchan/"
with open(ROOT + "boardlist") as f:
    BOARDS = load(f)
with open(ROOT + "postnums") as f:
    POSTS = load(f)

def setup_logging(default_path='logging.json', default_level=logging.INFO, env_key='LOG_CFG'):
    path = default_path
    value = getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)

def get_git_describe():
    """ Returns HTML string with current version. If on a tag: "v1.1.1"; if not on a tag or on untagged commit: "v1.1.1-1-abcdefgh" """
    name = '<a href="{}">{}</a> '.format(GH_URL, NAME)
    tag = check_output(["git", "describe", "--tags", "--always"], cwd=ROOT + ".web").strip().decode('utf-8')
    split = tag.split("-")
    def fmt_tag(tag):
        return '<a href="{0}/tree/{1}">{1}</a>'.format(GH_URL, tag)
    def fmt_commit(hash):
        return '<a href="{0}/commit/{1}">{1}</a>'.format(GH_URL, hash)
    def fmt_tagrevhash(tag, rev, hash):
        return '<a href="{0}/compare/{1}...{3}">{1}-{2}-{3}</a>'.format(GH_URL, tag, rev, hash)
    if len(split) == 1 and GH_URL:
        if split[0][0] == "v": # tag only
            return name + fmt_tag(split[0])
        elif len(split[0]) == 8: # commit hash
            return name + fmt_commit(split[0][1:])
        else: # unknown
            return name + split[0]
    elif len(split) == 3 and GH_URL: # tag-rev-hash
        split[2] = split[2][1:]
        return name + fmt_tagrevhash(*split)
    return name + tag

def get_board_nav(curboard):
    """Convenience function, passed into jinja"""
    boards = []
    for board in sorted(BOARDS.keys()):
        if board != curboard:
            boards.append('<a href="/{0}/">{0}</a>'.format(board))
        else:
            boards.append(board)
    return " / ".join(boards)

def get_form(board, id=None):
    """Convenience function, passed into jinja"""
    return render_template("submit.html", board=board, id=id)

def process_board(board_content):
    """Processes sshchan-format data and returns a dict"""
    toplevel = {}
    def fix_time(post):
        post["time"] = datetime.utcfromtimestamp(post["ts"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        post["ago"] = human(datetime.utcfromtimestamp(post["ts"]), precision=1)
    def clean_body(body):
        # Cross-board links: >>>(/)?boardname/id
        body = re.sub(r'>>>/?([a-zA-Z]{1,6})/(\d+)\b', r'<a class="ref" href="/\1/#\2">&gt;&gt;&gt;/\1/\2</a>', body)
        # Same-board links: >>id
        body = re.sub(r'>>(\d+)\b', r'<a class="ref" href="#\1">&gt;&gt;\1</a>', body)
        body = clean_html(html(body).strip())
        return body
    for post in board_content:
        postnum,title,*c = post
        ts,postnum,body = c.pop(0)
        htmlbody = clean_body(body)
        toplevel[postnum] = {}
        toplevel[postnum]["id"] = postnum
        toplevel[postnum]["title"] = title
        toplevel[postnum]["body"] = body
        toplevel[postnum]["htmlbody"] = htmlbody
        toplevel[postnum]["ts"] = int(ts)
        fix_time(toplevel[postnum])
        comments = []
        for ts,id,body in c:
            htmlbody = clean_body(body)
            out = {}
            out["ts"] = int(ts)
            fix_time(out)
            out["id"] = id
            out["body"] = body
            out["htmlbody"] = htmlbody
            out["name"] = "Anonymous"
            comments.append(out)
        toplevel[postnum]["comments"] = comments
        toplevel[postnum]["name"] = "Anonymous"
    return toplevel

app = Flask(__name__)
setup_logging()

with open("/home/blha303/sekritkee") as f:
    app.secret_key = f.read()
app.jinja_env.globals.update(info=get_git_describe, title="Chanweb", boardnav=get_board_nav, getform=get_form)
logging.debug("Imports done, flask loaded")

def invalid_board_name(board, desc=False):
    """Checks if a string meets our stringent standards.
    if desc = False, return True if string only contains characters in:
        ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
    if desc = True, same as above, but characters in:
        0123456789 .,'!/?
    are also allowed. """
    board_allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    desc_allowed = board_allowed + "0123456789 .,'!/?"
    if desc:
        return not board or not all((x in desc_allowed) for x in board) or len(board) > 30
    return not board or not board.isalpha() or not all((x in board_allowed) for x in board) or len(board) > 6 or board in BOARDS

@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "POST":
        global BOARDS
        global POSTS
        board = request.form["board"].lower() if request.form.get("board", None) else ""
        desc = request.form["desc"] if request.form.get("desc", None) else ""
        if board in BOARDS:
            flash("That board already exists!", "error")
            return render_template("newboard.html", board=board)
        if invalid_board_name(board) or invalid_board_name(desc, desc=True):
            if invalid_board_name(board):
                flash("Invalid board name! (alphabet, 1-6 characters, unique)", "error")
            if invalid_board_name(desc, desc=True):
                flash("Invalid description! (alphanumeripunctual, 1-30 chars)", "error")
            logging.debug("Someone tried to create an invalid board: {} ({})".format(board, desc))
            return render_template("newboard.html", board=board)
        try:
            mkdir(ROOT + "boards/" + board)
        except IOError:
            flash("Unable to create board :O", "error")
            logging.exception("User was unable to create board")
            return render_template("newboard.html", board=board)
        with open(ROOT + "boardlist", "w") as f:
            BOARDS[board] = desc
            dump(BOARDS, f)
        with open(ROOT + "boards/" + board + "/index", "w") as f:
            dump([[1, "GET", [int(datetime.timestamp(datetime.utcnow())), 1, "first"]]], f)
        with open(ROOT + "postnums", "w") as f:
            POSTS[board] = 1
            dump(POSTS, f)
        flash("Success? :O", "success")
        logging.info("New board created: " + board)
        return render_template("newboard.html", board=board)
    return render_template("index.html", boards=BOARDS)

@app.route('/<board>/', methods=["GET", "POST"])
def board_display(board):
    global BOARDS
    if board == "favicon.ico":
        return render_template("404.html"), 404
    with open(ROOT + "boardlist") as f:
        BOARDS = load(f)
    if board in BOARDS:
        desc = BOARDS[board]
        with open(ROOT + "boards/{}/index".format(board)) as f:
            board_content = load(f)
    else:
        return render_template("404.html"), 404

    if request.method == "POST":
        global POSTS
        title = request.form["title"] if request.form.get("title", None) else ""
        name = "Anonymous"
        body = request.form["body"] if request.form.get("body", None) else ""
        ip = request.headers.get("X-Forwarded-For", None)
        logging.info(ip)
        if not request.form.get("g-recaptcha-response", None):
            flash("You'll need to do something with the captcha please.", "error")
            return render_template("posted.html", board=board, desc=desc)
        try:
            with open("/home/blha303/recaptchakey") as f:
                captcha_resp = req_post("https://www.google.com/recaptcha/api/siteverify", data={"secret": f.read().strip(), "response": request.form.get("g-recaptcha-response"), "remoteip": ip}).json()
            if not captcha_resp["success"]:
                flash("Your captcha wasn't up to par. Want to try again? (You'll have to retype your message, sorry.)", "error")
                return render_template("posted.html", board=board, desc=desc)
        except:
            logging.exception("Error with captcha")
            flash("Sorry, there was a problem while processing the captcha. Please <a href='https://twitter.com/blha303'>let me know</a>.", "error")
            return render_template("posted.html", board=board, desc=desc)
        if '<div ' in body:
            flash("Hi there. Sorry to rain on your parade, but I can't let you do that. Soz.", "error")
            return render_template("posted.html", board=board, desc=desc)
        if clean_html(html(body).strip()) == "<div></div>":
            body = ""
        id = request.form["id"] if request.form.get("id", None) else ""
        if len(body) > 1500 or len(title) > 30 or len(name) > 30:
            flash("Too long! Want to try that again?", "error")
            return render_template("posted.html", board=board, desc=desc)
        if not body:
            flash("No body provided! We kinda need something there, sorry.", "error")
            return render_template("posted.html", board=board, desc=desc)
        if not board in POSTS:
            POSTS[board] = 1
        if id and id.isdigit():
            changed_something = False
            for post in board_content:
                if post[0] == int(id):
                    POSTS[board] += 1
                    post.append([int(datetime.timestamp(datetime.utcnow())),
                                 POSTS[board] + 1,
                                 body])
                    changed_something = True
            if not changed_something:
                flash("Sorry, couldn't find that top-level post.", "error")
                return render_template("posted.html", board=board, desc=desc)
        else:
            POSTS[board] += 1
            board_content.append([POSTS[board] + 1,
                                  title,
                                  [int(datetime.timestamp(datetime.utcnow())),
                                   POSTS[board] + 1,
                                   body]
                                 ])
        with open(ROOT + "postnums", "w") as f:
            dump(POSTS, f)
        with open(ROOT + "boards/{}/index".format(board), "w") as f:
            dump(board_content, f)
        flash("Success! (?)", "success")
        return render_template("posted.html", board=board, desc=desc, id=POSTS[board])

    toplevel = process_board(board_content)
    return render_template("board.html", posts=toplevel, board=board, desc=desc)

@app.route("/.well-known/acme-challenge/sKcvRiSjHFjRq6OvM1TXyotTxH08qN263Tp-cVPdkgM")
def acme():
    logging.info("Got an acme-challenge request")
    return "sKcvRiSjHFjRq6OvM1TXyotTxH08qN263Tp-cVPdkgM.--3x4yUIqI4PvD8bAfmTEZ2mwq3YoGv89krhoMNnlGI"

# http://flask.pocoo.org/snippets/45/
def request_wants_json():
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return request.args.get("json", False) or \
        (best == 'application/json' and
         request.accept_mimetypes[best] > request.accept_mimetypes['text/html'])

def api_endpoint_board(data):
    """/_api/board/{board} - Returns board contents. Currently does not allow POSTing (although /board/ accepts POSTs, but will return html). Send ?id=n to get #n (toplevel posts only)."""
    def error(code):
        """code: int http status code to return"""
        return jsonify({"error": code, "doc": api_endpoint_board.__doc__}), code
    if not data and not invalid_board_name(data): return error(400)
    if not data in BOARDS: return error(404)
    with open(ROOT + "boards/{}/index".format(data)) as f:
        board_content = process_board(load(f))
    postnum = request.args.get("id", None)
    if postnum:
        if not postnum.isdigit() or not int(postnum) in board_content:
            return error(404)
        return jsonify(board_content[int(postnum)])
    return jsonify(board_content)

endpoints = {'board': api_endpoint_board}

@app.route("/_api/")
def api_index():
    ep = {k: v.__doc__ for k,v in endpoints.items()}
    if request_wants_json():
        return jsonify(ep)
    return render_template("api.html", endpoints=ep)

@app.route("/_api/<endpoint>/<data>")
def api(endpoint, data):
    if endpoint in endpoints:
        return endpoints[endpoint](data)
    return jsonify({"error": 501, "doc": {k: v.__doc__ for k,v in endpoints.items()}}), 501

if __name__ == "__main__":
    app.run(port=56224, debug=True)
