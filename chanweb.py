#!/usr/bin/env python3

from flask import *
from json import load, dump
from subprocess import check_output

GH_URL = "https://github.com/blha303/sshchan-web"
ROOT = "/srv/sshchan/"

def get_git_describe():
    """ Returns HTML string with current version. If on a tag: "v1.1.1"; if not on a tag or on untagged commit: "v1.1.1-1-abcdefgh" """
    tag = check_output(["git", "describe", "--tags", "--always"], cwd="/srv/sshchan/.web").strip().decode('utf-8')
    split = tag.split("-")
    def fmt_tag(tag):
        return '<a href="{0}/tree/{1}">{1}</a>'.format(GH_URL, tag)
    def fmt_commit(hash):
        return '<a href="{0}/commit/{1}">{1}</a>'.format(GH_URL, hash)
    if len(split) == 1 and GH_URL:
        if split[0][0] == "v": # tag only
            return fmt_tag(split[0])
        elif len(split[0]) == 8: # commit hash
            return fmt_commit(split[0][1:])
        else: # unknown
            return split[0]
    elif len(split) == 3 and GH_URL: # tag-rev-hash
        return "-".join([fmt_tag(split[0]), split[1], fmt_commit(split[2][1:])])
    return tag

with open(ROOT + "boardlist") as f:
    BOARDS = load(f)

with open(ROOT + "postnums") as f:
    POSTS = load(f)

app = Flask(__name__)
app.jinja_env.globals.update(info=get_git_describe, title="Chanweb")

@app.route('/')
def index():
    return render_template("index.html", boards=BOARDS)

if __name__ == "__main__":
    app.run(port=56224, debug=True)
