from flask import Flask, g, request, render_template_string, make_response, jsonify
from functools import wraps
import requests
import sqlite3
import os
import json

DATABASE = os.getenv('DATABASE', 'app.db')
BASE_URI = os.getenv('BASE_URI', 'http://localhost/')
if BASE_URI.endswith('/'):
  BASE_URI = BASE_URI[:-1]

def bound(x,a,b):
  if x < a:
    return a
  if x > b:
    return b
  return x

def order(a,b):
  if a > b:
    return b, a
  return a, b

MIN_TOKEN_LIFETIME, MAX_TOKEN_LIFETIME = order(
  bound(int(os.getenv('MIN_TOKEN_LIFETIME',  300)),    5,  3600),
  bound(int(os.getenv('MAX_TOKEN_LIFETIME', 3600)), 3600, 86400))

# allow refresh at between 50% and 90% of lifetime
TOKEN_REFRESH_BUDGET = bound(int(os.getenv('TOKEN_REFRESH_BUDGET', 75)), 50, 90)

def expiry(t):
  return bound(int(int(t) / 100.0 * TOKEN_REFRESH_BUDGET), MIN_TOKEN_LIFETIME, MAX_TOKEN_LIFETIME)

def get_db():
  db = getattr(g, '_database', None)
  if db is None:
    db = g._database = sqlite3.connect(DATABASE)
  return db

def api_key_required(methods=[]):
  def wrapper(fn):
    @wraps(fn)
    def decorator(*args, **kwargs):
      if len(methods) > 0 and request.method not in methods:
        return fn(*args, **kwargs)

      key = None
      if 'authorization' in request.headers and request.headers['authorization'].startswith('API-Key '):
        key = request.headers['authorization'][8:]
      if key is None:
        return make_response(jsonify({'error': 'Authorization header required'}), 401)
      r = get_db().cursor().execute('select key from in_force_api_keys where key = ?', (key,))
      if r.fetchone() is None:
        return make_response(jsonify({'error': 'Authorization key invalid'}), 403)
      return fn(*args, **kwargs)
    return decorator
  return wrapper

class Handler():
  def __init__(self, url, kind, config):
    self.url = url
    self.kind = kind
    self.config = config

  def get(url, db):
    r = db.cursor().execute('''
      select url,
             kind,
             config_json
        from handlers
       where url = ?
    ''', (url,)).fetchone()
    if r is None:
      return None
    return Handler(r[0], r[1], json.loads(r[2]))

  def insert(self, db):
    db.cursor().execute('''
      insert into handlers
               (url, kind, config_json)
        values (?, ?, ?)
    ''', (self.url, self.kind, json.dumps(self.config)))
    db.commit()

  def ui(self, base_uri):
    return render_template_string('''<script>
const q = Object.fromEntries(
  document.location.search.replace(/^\?/, '').split('&').map(s => [
    decodeURIComponent(s.split(/=/, 2)[0]),
    decodeURIComponent(s.split(/=/, 2)[1]),
  ]));
if (!('t' in q)) {
  document.location.href = 'https://login.microsoftonline.com/{{ tenant_id }}/oauth2/v2.0/authorize' +
    '?client_id={{ client_id }}' +
    '&response_type=code' +
    '&response_mode=query' +
    '&redirect_uri=' + encodeURIComponent('{{ redirect_uri }}') +
    '&scope=' + encodeURIComponent('{{ scopes }}');
} else {
  document.write('<pre style="white-space: pre-wrap">');
  document.write(JSON.stringify(q, null, '  '));
  document.write('</pre>');
}</script>''',
    tenant_id    = self.config['tenant_id'],
    client_id    = self.config['client_id'],
    redirect_uri = '/'.join([base_uri, 'a', self.url]),
    scopes       = ' '.join(self.config['scopes'])
  )

  def exchange_code(self, id, code, base_uri):
    r = requests.post(
      f'https://login.microsoftonline.com/{self.config["tenant_id"]}/oauth2/v2.0/token',
      data={
        'tenant': self.config['tenant_id'],
        'client_id': self.config['client_id'],
        'client_secret': self.config['client_secret'],
        'code': code,
        'redirect_uri': '/'.join([base_uri, 'a', self.url]),
        'grant_type': 'authorization_code',
      }
    ).json()
    print('EXCHANGE CODE::')
    print(json.dumps(r, indent=2))

    got = self.config.copy()
    got['access_token'] = r['access_token']
    got['refresh_token'] = r['refresh_token']
    return Token('/'.join([self.url, id]), self.url, got), r['expires_in']


class Token():
  def __init__(self, url, handler_url, token):
    self.url = url
    self.handler_url = handler_url
    self.token = token

  def needing_refresh(db):
    r = db.cursor().execute('''
      select url,
             handler_url,
             token_json
        from tokens
       where refresh_after < current_timestamp
    ''')
    return [Token(t[0], t[1], json.loads(t[2])) for t in r]

  def get(url, db):
    r = db.cursor().execute('''
      select url,
             handler_url,
             token_json
        from tokens
       where url = ?
    ''', (url,)).fetchone()
    if r is None:
      return None
    return Token(r[0], r[1], json.loads(r[2]))

  def insert(self, db, expires_in):
    db.cursor().execute(f'''
      insert into tokens
               (url, handler_url, token_json,
                refresh_after)
        values (?, ?, ?,
                datetime(current_timestamp,
                         '+{expiry(expires_in)} seconds'))
    ''', (self.url, self.handler_url, json.dumps(self.token)))
    db.commit()

  def save(self, db, expires_in):
    db.cursor().execute(f'''
      update tokens
         set token_json = ?,
             refresh_after = datetime(current_timestamp, '+{expiry(expires_in)} seconds')
       where url = ?
    ''', (json.dumps(self.token), self.url))
    db.commit()

  def refresh(self, base_uri):
    r = requests.post(
      f'https://login.microsoftonline.com/{self.token["tenant_id"]}/oauth2/v2.0/token',
      data={
        'grant_type': 'refresh_token',
        'refresh_token': self.token['refresh_token'],
        'client_id': self.token['client_id'],
        'client_secret': self.token['client_secret'],
        'scope': ' '.join(self.token['scopes']),
        'redirect_uri': '/'.join([base_uri, 'a', self.handler_url]),
      }
    ).json()

    print('REFRESH TOKEN::')
    print(json.dumps(r, indent=2))

    self.token['access_token'] = r['access_token']
    self.token['refresh_token'] = r['refresh_token']
    return r['expires_in']

  def exportable(self, base_uri):
    return {
      'access_token': self.token['access_token'],
      'client_id':    self.token['client_id'],
      'scopes':       self.token['scopes'],
      'redirect_uri': '/'.join([base_uri, 'a', self.handler_url])
    }


app = Flask(__name__)

@app.teardown_appcontext
def close_connection(exception):
  db = getattr(g, '_database', None)
  if db is not None:
    db.close()

@app.route('/_/<path:url>', methods=['GET', 'POST'])
@api_key_required(methods=['POST'])
def ui(url):
  # url will come in with "/" list elements; this
  # split() call is [].split, not "".split
  url = '/'.join(url.split('/'))

  if request.method == 'GET':
    handler = Handler.get(url, get_db())
    if handler is None:
      return 'no dice.', 404
    return handler.ui(BASE_URI)

  elif request.method == 'POST':
    details = request.json
    handler = Handler(url, details['kind'], details['config'])
    handler.insert(get_db())
    return {'ok': 'created'}

  else:
    return 'method not allowed.'

@app.route('/a/<path:url>')
def auth(url):
  # url will come in with "/" list elements; this
  # split() call is [].split, not "".split
  url = '/'.join(url.split('/'))
  handler = Handler.get(url, get_db())
  if handler is None:
    return 'nope.', 404

  if request.args.get('code') is not None:
    token, expires_in = handler.exchange_code('t0', request.args.get('code'), BASE_URI)
    token.insert(get_db(), expires_in)
    return {'ok': 'created', 'url': token.url}

  return 'bad request.', 400

@app.route('/t/<path:url>')
@api_key_required()
def token(url):
  # url will come in with "/" list elements; this
  # split() call is [].split, not "".split
  url = '/'.join(url.split('/'))
  token = Token.get(url, get_db())
  if token is None:
    return {}, 404
  return token.exportable(BASE_URI)

@app.route('/r', methods=['POST'])
@api_key_required()
def refresh():
  r = []
  for token in Token.needing_refresh(get_db()):
    r.append(token.url)
    expires_in = token.refresh(BASE_URI)
    token.save(get_db(), expires_in)
  return r
