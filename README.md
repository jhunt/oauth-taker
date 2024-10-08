oauth-taker
===========

> I solemnly swear I am up to no good.

This project is an Oauth2 power tool for securing and refreshing
access tokens so that other services don't have to.  It uses
simple shared-key semantics for access control, and
conservatively refreshes tokens on a percentage budget approach.

Out of the box, the Flask app does nothing.  When you provide
Oauth2 application details (Client ID, Client Secret, etc.) and
properly configure your redirect URIs in the IdP to point to the
running app, things start to get interesting.

For example, assuming we have deployed and are accessible on
https://ot.example.com, we can set up a new app called 'foo':

```console
$ curl https://ot.example.com/_/foo \
       -H 'Content-Type: application/json' \
       -H 'Accept: application/json' \
       --data-binary=@handler.json
```

where `handler.json` looks something like this:

```json
{
  "kind": "microsoft/v1",
  "config": {
    "tenant_id": "your-ms-tenant-id",
    "client_id": "your-enterprise-app-client-id",
    "client_secret": "your-enterprise-app-client-secret",
    "scopes": [
      "https://graph.microsoft.com/Sites.Manage.All",
      "https://graph.microsoft.com/Files.ReadWrite.All",
      "https://graph.microsoft.com/TermStore.ReadWrite.All",
      "https://graph.microsoft.com/User.Read.All",
      "offline_access"
    ]
  }
}
```

This sets up the following new endpoints:

- `GET /_/foo` to provide the user interface for
  browser-facilitated authentication via the IdP
- `GET /a/foo` the callback URI that the IdP will follow (this
  needs to be added to your Azure Enteprise App definition)

Once the authentication has been done, a token named `t0` will be
saved to the local database, and accessible via authenticated
clients (see below) at `/t/foo/t0`.  It is my plan to add the
ability to name tokens during the UI setup phase and support
multiple tokens from the same Oauth2 app / client in the future.

To retrieve the actual access token, the `/_/foo/t0` endpoint
should be access via an HTTP GET request:

```console
$ curl -H 'Authorization: API-Key open-sesame (see below)' \
       -H 'Accept: application/json' \
       https://ot.example.com/_/foo/t0
{
  "access_token": "..."
}
```

What is returned aside from the `access_token` top-level key is
entirely left up to the implementation of the IdP handler.

Along with each token, Oauth-Taker also stores a timestamp for the
earliest possible refresh of that token.  This is calculated based
on the `expires_in` value we receive from the IdP and a budgeting
factor (which defaults to 75%).  For example, if we get a token
that is valid for 1,000 seconds, the earliest refresh on a 64%
budget would be 640 seconds.

All tokens that have passed their earliest refresh threshold can
be refreshed at once by posting (with API-Key authorization) to
the `/r` endpoint:

```console
$ curl -H 'Authorization: API-Key open-sesame (see below)' \
       -H 'Accept: application/json' \
       https://ot.example.com/r
[
  "foo/t0"
]
```

A list of all tokens refreshed (their relative URLs) is returned
upon success, and subsequent calls to the token-specific endpoint
(here, `/t/foo/t0`) will return the newly-refreshed access token
values.


## API Keys

API Keys are managed in the SQL database.  There is no user
interface (neither web nor CLI) for dealing with them.  I
personally use the `sqlite3` command-line and just write the SQL
to interrogate and manipulate the keystore.

Those queries are:

```sql
-- create a new valid api key of '12345'
insert into api_keys (shared_key, enabled_after, disabled_after)
  values ('12345', current_timestamp, '2030-12-31 23:59:59');

-- disable the api key 'c0mpr0m1s3d'
update api_keys
   set disabled_after = current_timestamp
 where shared_key = 'c0mpr0m1s3d';
```

Clients wishing to use an API key must supply an Authorization
header with a value formatted like this:

`API-Key $KEY`

where `$KEY` is the API key in the database's `shared_key` column.
No extra spacing is allowed.  The checker is VERY strict.

For example, to use the first key in the example above via curl,
you would run:

```console
$ curl -H 'Authorization: API-Key 12345' \
       # ... etc ...
```

The second key would not work, given that its `disabled_after`
date is now in the past.

## Operationalizing

A sample Docker Compose recipe is included in `contrib/`; it
defines the oauth-taker application itself (the `app` service) and
a small shell loop to refresh every X seconds, configurable.

The `refresh` service prints out some useful logs so that you can
see when and what is being refreshed.  Here's a sample transcript
from my own lab:

```
refresh-1  | fetch https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/APKINDEX.tar.gz
refresh-1  | fetch https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64/APKINDEX.tar.gz
refresh-1  | (1/10) Installing ca-certificates (20240705-r0)
refresh-1  | (2/10) Installing brotli-libs (1.1.0-r2)
refresh-1  | (3/10) Installing c-ares (1.28.1-r0)
refresh-1  | (4/10) Installing libunistring (1.2-r0)
refresh-1  | (5/10) Installing libidn2 (2.3.7-r0)
refresh-1  | (6/10) Installing nghttp2-libs (1.62.1-r0)
refresh-1  | (7/10) Installing libpsl (0.21.5-r1)
refresh-1  | (8/10) Installing zstd-libs (1.5.6-r0)
refresh-1  | (9/10) Installing libcurl (8.9.0-r0)
refresh-1  | (10/10) Installing curl (8.9.0-r0)
refresh-1  | Executing busybox-1.36.1-r29.trigger
refresh-1  | Executing ca-certificates-20240705-r0.trigger
refresh-1  | OK: 13 MiB in 24 packages
refresh-1  | [2024-08-13 18:46:47+0000] starting up; checking every 300 seconds.
refresh-1  | [2024-08-13 18:51:47+0000] []
refresh-1  | [2024-08-13 18:56:50+0000] []
refresh-1  | [2024-08-13 19:01:53+0000] []
refresh-1  | [2024-08-13 19:06:59+0000] []
refresh-1  | [2024-08-13 19:12:05+0000] []
refresh-1  | [2024-08-13 19:17:11+0000] []
refresh-1  | [2024-08-13 19:22:14+0000] []
refresh-1  | [2024-08-13 19:27:14+0000] ["vv/azure/t0"]
refresh-1  | [2024-08-13 19:32:15+0000] []
```
