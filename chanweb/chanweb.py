#!/usr/bin/env python3

from flask import *
from json import load, dump
from .util import get_git_describe

app = Flask(__name__)

with open("../sshchan.conf") as f:
    CONFIG = load(f)

with open(CONFIG["rootdir"] + "/boardlist") as f:
    BOARDS = load(f)

with open(CONFIG["rootdir"] + "/postnums") as f:
    POSTS = load(f)

@app.route('/')
def index():
    return render_template("index.html", boards=BOARDS)

def main():
    app.run(port=56224, debug=True)

if __name__ == "__main__":
    main()
