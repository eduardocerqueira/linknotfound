import logging
from flask import Flask, render_template, request, send_file
from linknotfound.storage import list_files, download_file, get_file
from linknotfound.util import LnfCfg

logging.basicConfig(
    format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)


def create_app():
    app = Flask(__name__)
    cfg = LnfCfg()

    @app.route("/")
    def home():
        contents = list_files(cfg)
        return render_template("home.html", contents=contents)

    @app.route("/get/<filename>", methods=["GET"])
    def get(filename):
        if request.method == "GET":
            data = get_file(filename, cfg)
            return render_template("report.html", data=data, title=filename)

    @app.route("/download/<filename>", methods=["GET"])
    def download(filename):
        if request.method == "GET":
            output = download_file(filename, cfg)
            return send_file(output, as_attachment=True)

    return app
