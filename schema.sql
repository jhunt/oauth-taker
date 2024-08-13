create table if not exists handlers (
  url         text not null unique,
  -- ui will be /_/$url
  -- callback will be /a/$url
  -- tokens will be /t/$url/$token
  kind        text not null,
  config_json text not null
);
create table if not exists tokens (
  url           text not null unique,
  handler_url   text not null,
  token_json    text not null,
  refresh_after timestamp not null
);

create table if not exists api_keys (
  shared_key      text,
  enabled_after   timestamp,
  disabled_after  timestamp,
  notes           text
);
drop view if exists in_force_api_keys;
create view in_force_api_keys as
select shared_key as key
  from api_keys
 where current_timestamp between enabled_after
                             and disabled_after
;
