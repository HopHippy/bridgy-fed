"""UI pages."""
import calendar
import datetime
from itertools import islice
import re
import urllib.parse

from flask import redirect, render_template, request
from google.cloud.ndb.stats import KindStat
from oauth_dropins.webutil import flask_util, logs, util
from oauth_dropins.webutil.flask_util import error
from oauth_dropins.webutil.util import json_dumps, json_loads

from app import app, cache
import common
from models import Follower, User, Activity

PAGE_SIZE = 20
FOLLOWERS_UI_LIMIT = 999


@app.route('/')
@flask_util.cached(cache, datetime.timedelta(days=1))
def front_page():
  """View for the front page."""
  return render_template('index.html')


@app.get(f'/responses/<regex("{common.DOMAIN_RE}"):domain>')  # deprecated
def user_deprecated(domain):
    return redirect(f'/user/{domain}', code=301)


@app.get(f'/user/<regex("{common.DOMAIN_RE}"):domain>')
def user(domain):
    if not User.get_by_id(domain):
      return render_template('user_not_found.html', domain=domain), 404

    query = Activity.query(
        Activity.status.IN(('new', 'complete', 'error')),
        Activity.domain == domain,
        )
    activities, before, after = fetch_page(query, Activity)

    followers = Follower.query(Follower.dest == domain)\
                        .count(limit=FOLLOWERS_UI_LIMIT)
    followers = f'{followers}{"+" if followers == FOLLOWERS_UI_LIMIT else ""}'

    following = Follower.query(Follower.src == domain)\
                        .count(limit=FOLLOWERS_UI_LIMIT)
    following = f'{following}{"+" if following == FOLLOWERS_UI_LIMIT else ""}'

    return render_template(
        'user.html',
        logs=logs,
        util=util,
        **locals(),
    )


@app.get(f'/user/<regex("{common.DOMAIN_RE}"):domain>/followers')
def followers(domain):
    # TODO:
    # pull more info from last_follow, eg name, profile picture, url
    # unify with following
    if not User.get_by_id(domain):
      return render_template('user_not_found.html', domain=domain), 404

    query = Follower.query(
        Follower.status == 'active',
        Follower.dest == domain,
    ).order(-Follower.updated)
    followers, before, after = fetch_page(query, Follower)

    for f in followers:
        f.url = f.src
        f.handle = re.sub(r'^https?://(.+)/(users/|@)(.+)$', r'@\3@\1', f.src)
        if f.last_follow:
            last_follow = json_loads(f.last_follow)
            f.picture = last_follow.get('actor', {}).get('icon', {}).get('url')

    return render_template(
        'followers.html',
        util=util,
        **locals()
    )


@app.get(f'/user/<regex("{common.DOMAIN_RE}"):domain>/following')
def following(domain):
    if not User.get_by_id(domain):
      return render_template('user_not_found.html', domain=domain), 404

    query = Follower.query(
        Follower.status == 'active',
        Follower.src == domain,
    ).order(-Follower.updated)
    followers, before, after = fetch_page(query, Follower)

    for f in followers:
        f.url = f.dest
        f.handle = re.sub(r'^https?://(.+)/(users/|@)(.+)$', r'@\3@\1', f.dest)

    return render_template(
        'following.html',
        util=util,
        **locals()
    )


@app.get('/responses')  # deprecated
def recent_deprecated():
    return redirect('/recent', code=301)


@app.get('/recent')
def recent():
    """Renders recent activities, with links to logs."""
    query = Activity.query(Activity.status.IN(('new', 'complete', 'error')))
    activities, before, after = fetch_page(query, Activity)
    return render_template(
        'recent.html',
        logs=logs,
        util=util,
        **locals(),
    )


def fetch_page(query, model_class):
    """Fetches a page of results from a datastore query.

    Uses the `before` and `after` query params (if provided; should be ISO8601
    timestamps) and the queried model class's `updated` property to identify the
    page to fetch.

    Populates a `log_url_path` property on each result entity that points to a
    its most recent logged request.

    Args:
      query: :class:`ndb.Query`
      model_class: ndb model class

    Returns:
      (results, new_before, new_after) tuple with:
      results: list of query result entities
      new_before, new_after: str query param values for `before` and `after`
        to fetch the previous and next pages, respectively
    """
    # if there's a paging param ('before' or 'after'), update query with it
    # TODO: unify this with Bridgy's user page
    def get_paging_param(param):
        val = request.values.get(param)
        try:
            return util.parse_iso8601(val.replace(' ', '+')) if val else None
        except BaseException:
            error(f"Couldn't parse {param}, {val!r} as ISO8601")

    before = get_paging_param('before')
    after = get_paging_param('after')
    if before and after:
        error("can't handle both before and after")
    elif after:
        query = query.filter(model_class.updated > after).order(-model_class.updated)
    elif before:
        query = query.filter(model_class.updated < before).order(-model_class.updated)
    else:
        query = query.order(-model_class.updated)

    query_iter = query.iter()
    results = sorted(islice(query_iter, 0, 20), key=lambda r: r.updated, reverse=True)

    # calculate new paging param(s)
    has_next = results and query_iter.probably_has_next()
    new_after = (
        before if before
        else results[0].updated if has_next and after
        else None)
    if new_after:
        new_after = new_after.isoformat()

    new_before = (
        after if after else
        results[-1].updated if has_next
        else None)
    if new_before:
        new_before = new_before.isoformat()

    return results, new_before, new_after


@app.get('/stats')
def stats():
   return render_template(
       'stats.html',
       users=KindStat.query(KindStat.kind_name == 'User').get().count,
       activities=KindStat.query(KindStat.kind_name == 'Activity').get().count,
       followers=KindStat.query(KindStat.kind_name == 'Follower').get().count,
   )


@app.get('/log')
@flask_util.cached(cache, logs.CACHE_TIME)
def log():
    return logs.log()