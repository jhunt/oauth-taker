Hello, fellow developer.  Here are some useful notes.

To spin up a dev copy, I recommend you build the Docker image and
spin that:

    $ IMAGE=oathdev make build
    $ rm -rf _dev
    $ docker stop oathdev
    $ docker rm   oathdev
    $ docker run -d --name oathdev \
        -v ./_dev/data:/data \
        -v ./app.py:/app/app.py:ro \
        -p 5009:5000 \
        oathdev
    $ echo "insert into api_keys (shared_key, enabled_after, disabled_after) values ('a-test-dev-apikey', current_timestamp, '2030-12-31 23:59:59');" \
      | sudo sqlite3 _dev/data/oauth.db

(All of this can be run via the `make dev` command, as well.)

Then, you can curl the localhost endpoint (or the remote IP of
your development server) to populate and test:

    $ curl http://localhost:5009/_/testing \
           -H 'Content-Type: application/json' \
           -H 'Accept: application/json' \
           --data-binary @dev.json

(Provided that you _have_ a `dev.json` file, of course)
