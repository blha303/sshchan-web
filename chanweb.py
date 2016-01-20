#!/usr/bin/env python3

import re
from flask import *
from json import load, dump
from subprocess import check_output
from datetime import datetime
from ago import human
from misaka import html
from lxml.html.clean import clean_html
from os import mkdir

GH_URL = "https://github.com/blha303/sshchan-web"
ROOT = "/home/blha303/sshchan/"
with open(ROOT + "boardlist") as f:
    BOARDS = load(f)
with open(ROOT + "postnums") as f:
    POSTS = load(f)

def get_git_describe():
    """ Returns HTML string with current version. If on a tag: "v1.1.1"; if not on a tag or on untagged commit: "v1.1.1-1-abcdefgh" """
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
            return fmt_tag(split[0])
        elif len(split[0]) == 8: # commit hash
            return fmt_commit(split[0][1:])
        else: # unknown
            return split[0]
    elif len(split) == 3 and GH_URL: # tag-rev-hash
        split[2] = split[2][1:]
        return fmt_tagrevhash(*split)
    return tag

def get_board_nav(curboard):
    boards = []
    for board in sorted(BOARDS.keys()):
        if board != curboard:
            boards.append('<a href="/{0}/">{0}</a>'.format(board))
        else:
            boards.append(board)
    return " / ".join(boards)

def get_form(board, id=None):
    return render_template("submit.html", board=board, id=id)

app = Flask(__name__)

with open("/home/blha303/sekritkee") as f:
    app.secret_key = f.read()
app.jinja_env.globals.update(info=get_git_describe, title="Chanweb", boardnav=get_board_nav, getform=get_form)

@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "POST":
        global BOARDS
        global POSTS
        board = request.form["board"].lower() if request.form.get("board", None) else ""
        desc = request.form["desc"] if request.form.get("desc", None) else ""
        if not board or not board.isalpha() or len(board) > 6 or board in BOARDS:
            flash("Invalid board name! (alphabet, 1-5 characters, unique)", "error")
            return render_template("newboard.html", board=board)
        if not desc or not all(x.isalpha() or x.isspace() for x in desc) or len(desc) > 30:
            flash("Invalid description! (alphanumerical, 1-30 chars)", "error")
            return render_template("newboard.html", board=board)
        try:
            mkdir(ROOT + "boards/" + board)
        except IOError:
            flash("Unable to create board :O", "error")
            return render_template("newboard.html", board=board)
        with open(ROOT + "boardlist", "w") as f:
            BOARDS[board] = desc
            dump(BOARDS, f)
        with open(ROOT + "boards/" + board + "/index", "w") as f:
            dump([], f)
        with open(ROOT + "postnums", "w") as f:
            POSTS[board] = 0
            dump(POSTS, f)
        flash("Success? :O", "success")
        return render_template("newboard.html", board=board)
    return render_template("index.html", boards=BOARDS)

@app.route('/<board>/', methods=["GET", "POST"])
def board_display(board):
    if board == "favicon.ico":
        return render_template("index.html", boards=BOARDS), 404
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
        if clean_html(html(body).strip()) == "<div></div>":
            body = ""
        id = request.form["id"] if request.form.get("id", None) else ""
        if len(body) > 1500 or len(title) > 30 or len(name) > 30:
            flash("Too long! Want to try that again?", "error")
            return render_template("posted.html", board=board, desc=desc)
        if not body:
            flash("No body provided! We kinda need something there, sorry.", "error")
            return render_template("posted.html", board=board, desc=desc)
        if id:
            if not id.isdigit():
                flash("Invalid request: ID not numeric", "error")
                return render_template("posted.html", board=board, desc=desc)
            changed_something = False
            for post in board_content:
                if post[0] == int(id):
                    post.append([int(datetime.timestamp(datetime.utcnow())),
                                 POSTS[board] + 1,
                                 body])
                    POSTS[board] += 1
                    changed_something = True
            if not changed_something:
                flash("Sorry, couldn't find that top-level post.", "error")
                return render_template("posted.html", board=board, desc=desc)
        else:
            board_content.append([POSTS[board] + 1,
                                  title,
                                  [int(datetime.timestamp(datetime.utcnow())),
                                   POSTS[board] + 1,
                                   body]
                                 ])
            POSTS[board] += 1
        with open(ROOT + "postnums", "w") as f:
            dump(POSTS, f)
        with open(ROOT + "boards/{}/index".format(board), "w") as f:
            dump(board_content, f)
        flash("Success! (?)", "success")
        return render_template("posted.html", board=board, desc=desc, id=POSTS[board])

    toplevel = {}
    def fix_time(post):
        post["time"] = datetime.utcfromtimestamp(post["ts"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        post["ago"] = human(datetime.utcfromtimestamp(post["ts"]), precision=1)
    for post in board_content:
        postnum,title,*c = post
        ts,postnum,body = c.pop(0)
        body = re.sub(r'>>(\d+?)', r'<a class="ref" href="#\1">&gt;&gt;\1</a>', body)
        body = clean_html(html(body).strip())
        toplevel[postnum] = {}
        toplevel[postnum]["id"] = postnum
        toplevel[postnum]["title"] = title
        toplevel[postnum]["body"] = body
        toplevel[postnum]["ts"] = int(ts)
        fix_time(toplevel[postnum])
        comments = []
        for ts,id,body in c:
            body = clean_html(html(body).strip())
            out = {}
            out["ts"] = int(ts)
            fix_time(out)
            out["id"] = id
            out["body"] = body
            out["name"] = "Anonymous"
            comments.append(out)
        toplevel[postnum]["comments"] = comments
        toplevel[postnum]["name"] = "Anonymous"
    return render_template("board.html", posts=toplevel, board=board, desc=desc)

@app.route("/.well-known/acme-challenge/sKcvRiSjHFjRq6OvM1TXyotTxH08qN263Tp-cVPdkgM")
def acme():
    return "sKcvRiSjHFjRq6OvM1TXyotTxH08qN263Tp-cVPdkgM.--3x4yUIqI4PvD8bAfmTEZ2mwq3YoGv89krhoMNnlGI"

if __name__ == "__main__":
    app.run(port=56224, debug=True)
