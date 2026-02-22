"""Home page back end."""

import flask

HOME = flask.Blueprint(
    name="home",
    import_name=__name__,
    url_prefix="/",
)


@HOME.route("/", methods=["GET"])
def home() -> str:
    """Home page rendering."""
    return flask.render_template("index.html")
