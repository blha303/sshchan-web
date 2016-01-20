#!/usr/bin/env python3

import re
from flask import *
from json import load, dump
from subprocess import check_output
from datetime import datetime
from ago import human
from jinja2 import evalcontextfilter, Markup, escape

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

def get_board_nav():
    return " / ".join(['<a href="/{0}/">{0}</a>'.format(board) for board in sorted(BOARDS.keys())])

app = Flask(__name__)
app.jinja_env.globals.update(info=get_git_describe, title="Chanweb", boardnav=get_board_nav)

_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')

@app.template_filter()
@evalcontextfilter
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', '<br>\n') \
        for p in _paragraph_re.split(escape(value)))
    if eval_ctx.autoescape:
        result = Markup(result)
    return result

@app.route('/')
def index():
    return render_template("index.html", boards=BOARDS)

@app.route('/<board>/')
def board_display(board):
    if board == "favicon.ico":
        return render_template("index.html", boards=BOARDS), 404
    if board in BOARDS:
        with open(ROOT + "boards/{}/index".format(board)) as f:
            board_content = load(f)
    toplevel = {}
    def fix_time(post):
        post["time"] = datetime.utcfromtimestamp(post["ts"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        post["ago"] = human(datetime.utcfromtimestamp(post["ts"]), precision=1)
    for post in board_content:
        postnum,title,*c = post
        ts,postnum,body = c.pop(0)
        toplevel[postnum] = {}
        toplevel[postnum]["id"] = postnum
        toplevel[postnum]["title"] = title
        toplevel[postnum]["body"] = body
        toplevel[postnum]["ts"] = int(ts)
        fix_time(toplevel[postnum])
        comments = []
        for ts,id,body in c:
            out = {}
            out["ts"] = int(ts)
            fix_time(out)
            out["id"] = id
            out["body"] = body
            out["name"] = "Anonymous"
            comments.append(out)
        toplevel[postnum]["comments"] = comments
        toplevel[postnum]["name"] = "Anonymous"
    return render_template("board.html", posts=toplevel, board=board)

if __name__ == "__main__":
    app.run(port=56224, debug=True)
